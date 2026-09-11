"""SQLite-backed play history: records what got generated, and turns that into
weights that favor tracks not heard recently for the generator's weighted-random
selection (see generator.py's `weights` parameter).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soundtrack_engine.models import Track

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "history.db"

# A track played very recently is never fully excluded, just heavily deprioritized —
# the pool might be too small to survive a hard cutoff.
_MIN_WEIGHT = 0.01


class PlayHistory:
    """Tracks which songs were selected for which progression/stage, and when."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: a single PlayHistory instance is only ever used
        # sequentially within one logical unit of work, but that work can legitimately
        # hop threads — e.g. FastAPI resolves a sync dependency in a worker thread
        # while an `async def` route handler runs on the event loop thread.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                progression_key TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                track_uri TEXT NOT NULL,
                played_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plays_stage_track "
            "ON plays(progression_key, stage_id, track_uri)"
        )
        self._conn.commit()

    def record_generation(
        self,
        progression_key: str,
        stage_id: str,
        tracks: list[Track],
        when: datetime | None = None,
    ) -> None:
        """Record that `tracks` were just selected for this progression/stage."""
        played_at = (when or datetime.now(timezone.utc)).isoformat()
        self._conn.executemany(
            "INSERT INTO plays (progression_key, stage_id, track_uri, played_at) "
            "VALUES (?, ?, ?, ?)",
            [(progression_key, stage_id, track.uri, played_at) for track in tracks],
        )
        self._conn.commit()

    def _last_played_at(self, progression_key: str, stage_id: str, track_uri: str) -> datetime | None:
        row = self._conn.execute(
            "SELECT MAX(played_at) FROM plays "
            "WHERE progression_key = ? AND stage_id = ? AND track_uri = ?",
            (progression_key, stage_id, track_uri),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def weights_for(
        self,
        progression_key: str,
        stage_id: str,
        tracks: list[Track],
        no_repeat_days: int,
        now: datetime | None = None,
    ) -> list[float]:
        """Weight each track for weighted-random selection: 1.0 if never played, or
        played >= no_repeat_days ago; ramping linearly down to _MIN_WEIGHT the more
        recently (within the window) it was played.
        """
        now = now or datetime.now(timezone.utc)
        weights: list[float] = []

        for track in tracks:
            last_played = self._last_played_at(progression_key, stage_id, track.uri)
            if last_played is None:
                weights.append(1.0)
                continue

            days_since = max((now - last_played).total_seconds() / 86400, 0)
            if days_since >= no_repeat_days:
                weights.append(1.0)
            else:
                fraction = days_since / no_repeat_days
                weights.append(_MIN_WEIGHT + (1.0 - _MIN_WEIGHT) * fraction)

        return weights

    def last_generated_at(self, progression_key: str) -> datetime | None:
        """When a progression was last rebuilt — the dashboard's "Last Generated"
        status, derived from existing play records rather than separate state.
        """
        row = self._conn.execute(
            "SELECT MAX(played_at) FROM plays WHERE progression_key = ?",
            (progression_key,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PlayHistory":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
