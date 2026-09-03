"""Domain types shared across the engine, independent of any Spotify SDK types."""

from __future__ import annotations

from pydantic import BaseModel


class Track(BaseModel):
    """A song as the rest of the engine needs to know it: URI and length."""

    uri: str
    duration_ms: int
