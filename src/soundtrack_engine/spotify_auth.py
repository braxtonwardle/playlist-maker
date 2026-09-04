"""Spotify OAuth: interactive login (Authorization Code flow) and token refresh.

Only this module and spotify_api_client.py know about Spotify's HTTP API — every
other module talks to Spotify through the SpotifyClient protocol instead.
"""

from __future__ import annotations

import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from soundtrack_engine.token_store import load_tokens, save_tokens

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = (
    "playlist-read-private playlist-read-collaborative "
    "playlist-modify-public playlist-modify-private"
)
REFRESH_MARGIN_SECONDS = 60


class MissingCredentialsError(RuntimeError):
    """Raised when SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET aren't set."""


def _client_credentials() -> tuple[str, str]:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise MissingCredentialsError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set (see .env.example)."
        )
    return client_id, client_secret


def login(redirect_uri: str) -> None:
    """Interactive OAuth login: opens a browser, waits for the redirect, saves tokens."""
    client_id, client_secret = _client_credentials()

    auth_url = f"{AUTHORIZE_URL}?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
        }
    )

    print(f"Open this URL to authorize (attempting to open it automatically):\n{auth_url}\n")
    webbrowser.open(auth_url)

    code = _wait_for_callback(urlparse(redirect_uri))

    response = requests.post(
        TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        auth=(client_id, client_secret),
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    save_tokens(
        {
            "access_token": payload["access_token"],
            "refresh_token": payload["refresh_token"],
            "expires_at": time.time() + payload["expires_in"],
        }
    )
    print("Logged in. Tokens saved to .spotify-tokens.json.")


def _wait_for_callback(parsed_redirect) -> str:
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 — required name for BaseHTTPRequestHandler
            query = parse_qs(urlparse(self.path).query)
            if "code" in query:
                result["code"] = query["code"][0]
                body = b"Login successful \xe2\x80\x94 you can close this tab."
            else:
                result["error"] = query.get("error", ["unknown_error"])[0]
                body = b"Login failed, check the terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass  # silence default request logging to stderr

    host = parsed_redirect.hostname or "127.0.0.1"
    port = parsed_redirect.port or 80
    server = HTTPServer((host, port), Handler)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        raise RuntimeError(f"Spotify authorization failed: {result['error']}")
    return result["code"]


def get_access_token() -> str:
    """Return a valid access token, refreshing it first if it's expired or missing."""
    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError("Not logged in yet — run `soundtrack-engine login` first.")

    if time.time() < tokens["expires_at"] - REFRESH_MARGIN_SECONDS:
        return tokens["access_token"]

    client_id, client_secret = _client_credentials()
    response = requests.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        auth=(client_id, client_secret),
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    updated = {
        "access_token": payload["access_token"],
        # Spotify doesn't always return a new refresh_token; keep the old one if absent.
        "refresh_token": payload.get("refresh_token", tokens["refresh_token"]),
        "expires_at": time.time() + payload["expires_in"],
    }
    save_tokens(updated)
    return updated["access_token"]
