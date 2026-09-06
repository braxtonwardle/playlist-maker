"""The concrete SpotifyClient: the only class that actually calls Spotify's Web API."""

from __future__ import annotations

from typing import Callable

import requests

from soundtrack_engine.models import Track
from soundtrack_engine.spotify_auth import get_access_token

API_BASE = "https://api.spotify.com/v1"
MAX_TRACKS_PER_REPLACE_REQUEST = 100


class SpotifyApiClient:
    """Implements the SpotifyClient protocol against the real Spotify Web API."""

    def __init__(self, access_token_provider: Callable[[], str] = get_access_token) -> None:
        self._access_token_provider = access_token_provider

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token_provider()}"}

    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return every track currently in the given playlist, in playlist order."""
        tracks: list[Track] = []
        # Spotify's newer API surface renamed this sub-resource from /tracks to
        # /items; this app gets 403s on /tracks (confirmed against a real playlist)
        # but /items works identically.
        url: str | None = f"{API_BASE}/playlists/{playlist_id}/items"
        params: dict[str, object] | None = {
            "fields": "items(track(uri,duration_ms,is_local)),next",
            "limit": 100,
        }

        while url:
            response = requests.get(url, headers=self._headers(), params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()

            for item in payload["items"]:
                track = item.get("track")
                if track and not track.get("is_local") and track.get("uri"):
                    tracks.append(Track(uri=track["uri"], duration_ms=track["duration_ms"]))

            url = payload.get("next")
            params = None  # `next` is already a full URL with its query params baked in

        return tracks

    def replace_playlist_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        """Overwrite the given playlist's contents with this ordered list of URIs."""
        if len(track_uris) > MAX_TRACKS_PER_REPLACE_REQUEST:
            raise ValueError(
                f"got {len(track_uris)} track URIs; replace_playlist_tracks only supports "
                f"up to {MAX_TRACKS_PER_REPLACE_REQUEST} in a single call"
            )

        response = requests.put(
            f"{API_BASE}/playlists/{playlist_id}/items",
            headers=self._headers(),
            json={"uris": track_uris},
            timeout=10,
        )
        response.raise_for_status()

    # --- One-time setup helpers, not part of the SpotifyClient protocol: the ---
    # --- generator/history/publishing phases never need to create a playlist. ---

    def get_current_user_id(self) -> str:
        response = requests.get(f"{API_BASE}/me", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()["id"]

    def get_playlist_name(self, playlist_id: str) -> str:
        response = requests.get(
            f"{API_BASE}/playlists/{playlist_id}",
            headers=self._headers(),
            params={"fields": "name"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["name"]

    def create_playlist(
        self, user_id: str, name: str, description: str = "", public: bool = False
    ) -> str:
        response = requests.post(
            f"{API_BASE}/users/{user_id}/playlists",
            headers=self._headers(),
            json={"name": name, "description": description, "public": public},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["id"]
