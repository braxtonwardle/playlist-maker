"""YAML-backed configuration schema for progressions, stages, and Spotify settings.

A "progression" (e.g. Morning, Night) is an ordered list of "stages" (emotional
moods). Each stage names a source Spotify playlist to pull songs from and either a
target duration in minutes, or `open_ended: true` for a stage (like Night's
"Reading / journaling") that has no fixed length.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Stage(BaseModel):
    """One emotional stage within a progression, backed by a source playlist."""

    name: str
    source_playlist_id: str = ""
    target_minutes: float | None = None
    open_ended: bool = False
    seed_songs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_duration(self) -> "Stage":
        if self.open_ended and self.target_minutes is not None:
            raise ValueError(
                f'stage "{self.name}" is open_ended and must not set target_minutes'
            )
        if not self.open_ended and self.target_minutes is None:
            raise ValueError(
                f'stage "{self.name}" needs target_minutes (or set open_ended: true)'
            )
        if self.target_minutes is not None and self.target_minutes <= 0:
            raise ValueError(f'stage "{self.name}" target_minutes must be positive')
        return self


class Progression(BaseModel):
    """An ordered mood arc (e.g. Morning) that generates into one output playlist."""

    output_playlist_id: str = ""
    output_playlist_name: str
    stages: list[Stage]

    @field_validator("stages")
    @classmethod
    def _non_empty(cls, stages: list[Stage]) -> list[Stage]:
        if not stages:
            raise ValueError("a progression needs at least one stage")
        return stages


class SpotifySettings(BaseModel):
    """Non-secret Spotify settings. Client ID/secret live in the environment, not here."""

    redirect_uri: str = "http://127.0.0.1:8888/callback"


class Config(BaseModel):
    no_repeat_days: int = 15
    spotify: SpotifySettings = Field(default_factory=SpotifySettings)
    progressions: dict[str, Progression]

    @field_validator("no_repeat_days")
    @classmethod
    def _positive_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("no_repeat_days must be positive")
        return value

    @field_validator("progressions")
    @classmethod
    def _non_empty_progressions(cls, progressions: dict[str, Progression]) -> dict[str, Progression]:
        if not progressions:
            raise ValueError("config needs at least one progression")
        return progressions


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML config file into a Config."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return Config.model_validate(raw)
