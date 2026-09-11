"""Pure logic for applying the dashboard's stage-duration edits to a Progression,
kept separate from the FastAPI route so it's testable without an HTTP layer.
Reuses Stage's own Pydantic validation (positive minutes, open_ended/target_minutes
mutual exclusivity) rather than re-implementing those rules here.
"""

from __future__ import annotations

from dataclasses import dataclass

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
