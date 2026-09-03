"""The single interface the rest of the engine uses to talk to Spotify.

Implemented in Phase 2. Every other module — the generator (Phase 3), history
(Phase 4), publishing (Phase 5) — depends only on this protocol and on `Track`
from `models.py`, never on a Spotify SDK or raw HTTP calls. That keeps Spotify
integration in one place instead of leaking through the codebase.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from soundtrack_engine.models import Track


@runtime_checkable
class SpotifyClient(Protocol):
    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Return every track currently in the given playlist, in playlist order."""
        ...

    def replace_playlist_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        """Overwrite the given playlist's contents with this ordered list of URIs."""
        ...
