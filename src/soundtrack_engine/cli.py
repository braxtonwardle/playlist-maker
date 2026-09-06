"""Command-line entry points for the engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

from soundtrack_engine.bootstrap import bootstrap_playlists
from soundtrack_engine.config import load_config
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.logging_setup import configure_logging
from soundtrack_engine.publish import rebuild_progression
from soundtrack_engine.spotify_api_client import SpotifyApiClient
from soundtrack_engine.spotify_auth import MissingCredentialsError
from soundtrack_engine.spotify_auth import login as spotify_login

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
CONFIG_PATH = Path("config/config.yaml")
CONFIG_EXAMPLE_PATH = Path("config/config.example.yaml")


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


def _cmd_bootstrap_playlists(args: argparse.Namespace) -> None:
    """Create any playlist config.yaml references but doesn't have an id for yet."""
    source_path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    if source_path is CONFIG_EXAMPLE_PATH:
        print(f"No {CONFIG_PATH} yet — starting from {CONFIG_EXAMPLE_PATH}")

    config = load_config(source_path)
    client = SpotifyApiClient()
    user_id = client.get_current_user_id()

    created = bootstrap_playlists(config, client, user_id)

    CONFIG_PATH.write_text(
        yaml.safe_dump(config.model_dump(mode="python"), sort_keys=False),
        encoding="utf-8",
    )

    if created:
        print(f"Created {len(created)} playlist(s):")
        for name, playlist_id in created:
            print(f"  {name}: {playlist_id}")
    else:
        print("Nothing to create — every stage and output already has a playlist id.")
    print(f"Wrote {CONFIG_PATH}")


def _cmd_generate(args: argparse.Namespace) -> None:
    """Rebuild one progression's output playlist from its current stage pools."""
    config = load_config(CONFIG_PATH)
    client = SpotifyApiClient()
    history = PlayHistory()

    tracks = rebuild_progression(args.progression, config, client, history)

    minutes, seconds = divmod(sum(t.duration_ms for t in tracks) // 1000, 60)
    progression = config.progressions[args.progression]
    print(
        f"Wrote {len(tracks)} tracks ({minutes}m{seconds:02d}s) to "
        f"\"{progression.output_playlist_name}\""
    )


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

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-playlists",
        help="Create any missing source/output playlists from config and save their ids",
    )
    bootstrap_parser.set_defaults(func=_cmd_bootstrap_playlists)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Rebuild a progression's output playlist from its current stage pools",
    )
    generate_parser.add_argument("progression", choices=["morning", "night"])
    generate_parser.set_defaults(func=_cmd_generate)

    return parser


def main() -> None:
    # override=True: .env is the authoritative source, even if the shell already has
    # (possibly stale/empty) same-named variables set — e.g. from an editor's terminal
    # env-file injection that ran before .env had real values.
    load_dotenv(override=True)
    configure_logging()
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (MissingCredentialsError, RuntimeError, requests.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
