"""YAML-backed configuration schema for progressions, stages, and generator settings.

A "progression" (e.g. Morning, Night) is an ordered list of "stages" (emotional
moods). Each stage names a source Spotify playlist to pull songs from and either a
target duration in minutes, or `open_ended: true` for a stage (like Night's
"Reading / journaling") that has no fixed length.

Config only ever holds playlist ids, stage order, durations, and generator settings.
Spotify itself is the source of truth for what songs are actually in a stage's pool —
config never lists songs.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_STAGE_ID_PATTERN = re.compile(r"[a-z0-9_]+")


class Stage(BaseModel):
    """One emotional stage within a progression, backed by a source playlist.

    `id` is a stable identifier (e.g. for history/DB rows in later phases) that
    stays fixed even if `name`, the human-readable display label, changes later.
    """

    id: str
    name: str
    source_playlist_id: str = ""
    target_minutes: float | None = None
    open_ended: bool = False

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _STAGE_ID_PATTERN.fullmatch(value):
            raise ValueError(
                f'stage id "{value}" must be lowercase snake_case (letters, digits, underscores only)'
            )
        return value

    @model_validator(mode="after")
    def _check_duration(self) -> "Stage":
        if self.open_ended and self.target_minutes is not None:
            raise ValueError(
                f'stage "{self.id}" is open_ended and must not set target_minutes'
            )
        if not self.open_ended and self.target_minutes is None:
            raise ValueError(
                f'stage "{self.id}" needs target_minutes (or set open_ended: true)'
            )
        if self.target_minutes is not None and self.target_minutes <= 0:
            raise ValueError(f'stage "{self.id}" target_minutes must be positive')
        return self


class Progression(BaseModel):
    """An ordered mood arc (e.g. Morning) that generates into one output playlist."""

    output_playlist_id: str = ""
    output_playlist_name: str
    stages: list[Stage]

    @field_validator("stages")
    @classmethod
    def _non_empty_and_unique_ids(cls, stages: list[Stage]) -> list[Stage]:
        if not stages:
            raise ValueError("a progression needs at least one stage")
        ids = [stage.id for stage in stages]
        duplicates = {stage_id for stage_id in ids if ids.count(stage_id) > 1}
        if duplicates:
            raise ValueError(f"duplicate stage ids: {sorted(duplicates)}")
        return stages


class SpotifySettings(BaseModel):
    """Non-secret Spotify settings. Client ID/secret live in the environment, not here."""

    redirect_uri: str = "http://127.0.0.1:8888/callback"


class GeneratorSettings(BaseModel):
    """Tunable knobs for playlist generation. Home for future generator settings."""

    no_repeat_days: int = 15
    duration_tolerance_minutes: float = 2.0

    @field_validator("no_repeat_days")
    @classmethod
    def _positive_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("no_repeat_days must be positive")
        return value

    @field_validator("duration_tolerance_minutes")
    @classmethod
    def _positive_tolerance(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("duration_tolerance_minutes must be positive")
        return value


class Config(BaseModel):
    spotify: SpotifySettings = Field(default_factory=SpotifySettings)
    generator: GeneratorSettings = Field(default_factory=GeneratorSettings)
    progressions: dict[str, Progression]

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
