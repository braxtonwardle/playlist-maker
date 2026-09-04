"""Command-line entry points for the engine."""

from __future__ import annotations

import argparse
import sys

import requests
from dotenv import load_dotenv

from soundtrack_engine.logging_setup import configure_logging
from soundtrack_engine.spotify_api_client import SpotifyApiClient
from soundtrack_engine.spotify_auth import MissingCredentialsError
from soundtrack_engine.spotify_auth import login as spotify_login

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def _cmd_login(args: argparse.Namespace) -> None:
    spotify_login(args.redirect_uri)


def _cmd_show_playlist(args: argparse.Namespace) -> None:
    """Sanity-check a playlist id by listing its tracks and total duration."""
    client = SpotifyApiClient()
    tracks = client.fetch_playlist_tracks(args.playlist_id)
    minutes, seconds = divmod(sum(t.duration_ms for t in tracks) // 1000, 60)
    print(f"{len(tracks)} tracks, {minutes}m{seconds:02d}s total")
    for track in tracks:
        print(f"  {track.uri}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soundtrack-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Authenticate with Spotify")
    login_parser.add_argument("--redirect-uri", dest="redirect_uri", default=DEFAULT_REDIRECT_URI)
    login_parser.set_defaults(func=_cmd_login)

    show_parser = subparsers.add_parser(
        "show-playlist",
        help="List a playlist's tracks and total duration (sanity check a playlist id)",
    )
    show_parser.add_argument("playlist_id")
    show_parser.set_defaults(func=_cmd_show_playlist)

    return parser


def main() -> None:
    load_dotenv()
    configure_logging()
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (MissingCredentialsError, RuntimeError, requests.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
