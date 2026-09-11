"""FastAPI dependency providers. Routes depend on these functions rather than
constructing SpotifyApiClient/PlayHistory/config directly, so tests can swap in
fakes via `app.dependency_overrides` without touching real Spotify or disk state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from fastapi import Depends

from soundtrack_engine.config import Config, load_config, resolve_config_path
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.spotify_api_client import SpotifyApiClient
from soundtrack_engine.spotify_client import SpotifyClient


def get_config_path() -> Path:
    return resolve_config_path()


def get_config(config_path: Path = Depends(get_config_path)) -> Config:
    return load_config(config_path)


def get_spotify_client() -> SpotifyClient:
    return SpotifyApiClient()


def get_history() -> Iterator[PlayHistory]:
    history = PlayHistory()
    try:
        yield history
    finally:
        history.close()
