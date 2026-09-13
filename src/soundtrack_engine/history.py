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
        """Record that `tracks` were just selected for this progression/stage. Any
        earlier record for this same progression/stage on the same calendar day is
        replaced rather than added to — regenerating from the dashboard multiple
        times in one day (e.g. while tweaking a stage) should count as one "played
        today" for no-repeat purposes, not one per tap, which would otherwise
        suppress every track from every regeneration for the next no_repeat_days.
        """
        when = when or datetime.now(timezone.utc)
        played_at = when.isoformat()
        day = when.date().isoformat()
        self._conn.execute(
            "DELETE FROM plays WHERE progression_key = ? AND stage_id = ? AND date(played_at) = ?",
            (progression_key, stage_id, day),
        )
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

    def latest_run_stage_sequence(self, progression_key: str) -> list[tuple[str, str]]:
        """Return (track_uri, stage_id) pairs recorded by the most recent generation
        run for this progression, in the order they were written. A run's stages
        all share one `played_at` (rebuild_progression computes it once up front),
        so this only ever spans a single generation, never accumulating across
        days. A song picked by two different stages in that one run — e.g. briefly
        present in both an open-ended stage's pool and an earlier stage's, before
        being removed from one — appears twice here, once per stage: callers
        should consume this positionally against the live playlist rather than
        collapsing it into a uri-keyed dict, so each physical occurrence gets
        matched to the stage that actually picked it.
        """
        row = self._conn.execute(
            "SELECT MAX(played_at) FROM plays WHERE progression_key = ?", (progression_key,)
        ).fetchone()
        if row is None or row[0] is None:
            return []
        latest_played_at = row[0]
        rows = self._conn.execute(
            "SELECT track_uri, stage_id FROM plays WHERE progression_key = ? AND played_at = ? "
            "ORDER BY id ASC",
            (progression_key, latest_played_at),
        ).fetchall()
        return [(uri, stage_id) for uri, stage_id in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PlayHistory":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
