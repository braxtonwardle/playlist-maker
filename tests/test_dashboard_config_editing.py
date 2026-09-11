import pytest
from pydantic import ValidationError

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.dashboard.config_editing import (
    StageEditNotAllowed,
    StageUpdate,
    apply_stage_updates,
)


def _progression() -> Progression:
    stages = [
        Stage(id="a", name="A", source_playlist_id="pool-a", target_minutes=10),
        Stage(id="b", name="B", source_playlist_id="pool-b", target_minutes=10),
        Stage(id="c", name="C", source_playlist_id="pool-c", target_minutes=10),
    ]
    return Progression(output_playlist_name="Test", output_playlist_id="out-1", stages=stages)


def test_updates_target_minutes_for_each_stage() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=False, target_minutes=12),
        StageUpdate(stage_id="b", open_ended=False, target_minutes=8),
        StageUpdate(stage_id="c", open_ended=False, target_minutes=5),
    ]

    result = apply_stage_updates(progression, updates)

    assert [s.target_minutes for s in result.stages] == [12, 8, 5]
    # source_playlist_id / order / names are untouched
    assert [s.id for s in result.stages] == ["a", "b", "c"]
    assert result.stages[0].source_playlist_id == "pool-a"


def test_first_stage_may_become_open_ended() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=True, target_minutes=None),
        StageUpdate(stage_id="b", open_ended=False, target_minutes=8),
        StageUpdate(stage_id="c", open_ended=False, target_minutes=5),
    ]

    result = apply_stage_updates(progression, updates)

    assert result.stages[0].open_ended is True
    assert result.stages[0].target_minutes is None


def test_last_stage_may_become_open_ended() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=False, target_minutes=10),
        StageUpdate(stage_id="b", open_ended=False, target_minutes=8),
        StageUpdate(stage_id="c", open_ended=True, target_minutes=None),
    ]

    result = apply_stage_updates(progression, updates)

    assert result.stages[-1].open_ended is True


def test_middle_stage_rejects_open_ended() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=False, target_minutes=10),
        StageUpdate(stage_id="b", open_ended=True, target_minutes=None),
        StageUpdate(stage_id="c", open_ended=False, target_minutes=5),
    ]

    with pytest.raises(StageEditNotAllowed):
        apply_stage_updates(progression, updates)


def test_missing_stage_update_rejected() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=False, target_minutes=10),
        StageUpdate(stage_id="b", open_ended=False, target_minutes=8),
    ]

    with pytest.raises(StageEditNotAllowed):
        apply_stage_updates(progression, updates)


def test_non_positive_minutes_rejected_by_stage_validation() -> None:
    progression = _progression()
    updates = [
        StageUpdate(stage_id="a", open_ended=False, target_minutes=0),
        StageUpdate(stage_id="b", open_ended=False, target_minutes=8),
        StageUpdate(stage_id="c", open_ended=False, target_minutes=5),
    ]

    with pytest.raises(ValidationError):
        apply_stage_updates(progression, updates)
