"""Domain types shared across the engine, independent of any Spotify SDK types."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Track(BaseModel):
    """A song as the rest of the engine needs to know it: URI, length, primary
    artist id (for spacing same-artist tracks apart within a stage's picks), and
    enough display metadata (name/artists) for the dashboard to show a track list
    without a separate Spotify lookup. Everything but uri/duration_ms defaults to
    empty since most of the engine (generator, history) only needs those two.
    """

    uri: str
    duration_ms: int
    name: str = ""
    artists: list[str] = Field(default_factory=list)
    artist_id: str = ""


class StageResult(BaseModel):
    """One stage's generated tracks, tagged with which stage they came from — lets
    callers (the dashboard, in particular) show a track list grouped/labeled by
    stage without re-deriving that from config.
    """

    stage_id: str
    stage_name: str
    tracks: list[Track]
