"""One-time setup: create any Spotify playlists config doesn't have an id for yet."""

from __future__ import annotations

from typing import Protocol

from soundtrack_engine.config import Config


class PlaylistCreator(Protocol):
    def create_playlist(self, user_id: str, name: str, description: str = "") -> str: ...


def bootstrap_playlists(config: Config, client: PlaylistCreator, user_id: str) -> list[tuple[str, str]]:
    """Fill in any blank output_playlist_id/source_playlist_id fields in `config` by
    creating a real Spotify playlist for each. Mutates `config` in place; entries
    that already have an id are left untouched. Returns (name, id) for everything
    newly created.
    """
    created: list[tuple[str, str]] = []

    for progression_key, progression in config.progressions.items():
        if not progression.output_playlist_id:
            playlist_id = client.create_playlist(
                user_id,
                progression.output_playlist_name,
                description=f"Soundtrack Engine output playlist: {progression_key}",
            )
            progression.output_playlist_id = playlist_id
            created.append((progression.output_playlist_name, playlist_id))

        for stage in progression.stages:
            if not stage.source_playlist_id:
                name = f"[Soundtrack] {progression_key.capitalize()} — {stage.name}"
                playlist_id = client.create_playlist(
                    user_id,
                    name,
                    description=f"Soundtrack Engine source pool: {progression_key}/{stage.id}",
                )
                stage.source_playlist_id = playlist_id
                created.append((name, playlist_id))

    return created
