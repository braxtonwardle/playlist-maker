"""Pure logic for applying the dashboard's stage-duration edits to a Progression,
kept separate from the FastAPI route so it's testable without an HTTP layer.
Reuses Stage's own Pydantic validation (positive minutes, open_ended/target_minutes
mutual exclusivity) rather than re-implementing those rules here.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from soundtrack_engine.config import Progression, Stage


@dataclass
class StageUpdate:
    stage_id: str
    open_ended: bool
    target_minutes: float | None


class StageEditNotAllowed(ValueError):
    """Raised when an edit violates a dashboard-level rule (e.g. only the first and
    last stage of a progression may be open-ended) — distinct from a Stage schema
    validation error, though both are handled as a 422 by the route.
    """


def apply_stage_updates(progression: Progression, updates: list[StageUpdate]) -> Progression:
    """Return a new Progression with each stage's duration/open-ended state replaced
    per `updates`. Stage id, name, source playlist, and stage order are untouched —
    the dashboard only tunes timing, it doesn't add/remove/reorder stages.
    """
    by_id = {update.stage_id: update for update in updates}
    first_id = progression.stages[0].id
    last_id = progression.stages[-1].id

    new_stages: list[Stage] = []
    for stage in progression.stages:
        update = by_id.get(stage.id)
        if update is None:
            raise StageEditNotAllowed(f'missing update for stage "{stage.id}"')
        if update.open_ended and stage.id not in (first_id, last_id):
            raise StageEditNotAllowed(
                f'stage "{stage.id}" may not be open-ended — only the first and '
                f"last stage of a progression can be"
            )
        new_stages.append(
            Stage(
                id=stage.id,
                name=stage.name,
                source_playlist_id=stage.source_playlist_id,
                open_ended=update.open_ended,
                target_minutes=None if update.open_ended else update.target_minutes,
            )
        )

    return progression.model_copy(update={"stages": new_stages})


def backup_config(config_path: Path) -> Path | None:
    """Copy the current config file into a `backups/` folder next to it before a
    Save overwrites it, so a bad edit is always one file-copy away from undone.
    Returns the backup's path, or None if there was nothing to back up yet (the
    very first save, before config_path exists).
    """
    if not config_path.exists():
        return None

    backup_dir = config_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"{config_path.stem}.{timestamp}{config_path.suffix}"
    shutil.copy2(config_path, backup_path)
    return backup_path
