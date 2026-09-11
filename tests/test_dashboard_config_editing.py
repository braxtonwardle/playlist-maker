import time

import pytest
from pydantic import ValidationError

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.dashboard.config_editing import (
    StageEditNotAllowed,
    StageUpdate,
    apply_stage_updates,
    backup_config,
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


def test_backup_config_returns_none_when_nothing_to_back_up(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"  # doesn't exist yet

    assert backup_config(config_path) is None
    assert not (tmp_path / "backups").exists()


def test_backup_config_copies_current_content_into_backups_dir(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("progressions: {}\n", encoding="utf-8")

    backup_path = backup_config(config_path)

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "backups"
    assert backup_path.read_text(encoding="utf-8") == "progressions: {}\n"
    assert backup_path.name.startswith("config.")
    assert backup_path.suffix == ".yaml"


def test_backup_config_does_not_touch_the_live_file(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("original\n", encoding="utf-8")

    backup_config(config_path)

    assert config_path.read_text(encoding="utf-8") == "original\n"


def test_backup_config_multiple_saves_produce_multiple_backups(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"

    config_path.write_text("version-1\n", encoding="utf-8")
    first_backup = backup_config(config_path)
    time.sleep(0.001)  # ensure a distinct microsecond-precision timestamp
    config_path.write_text("version-2\n", encoding="utf-8")
    second_backup = backup_config(config_path)

    assert first_backup != second_backup
    assert first_backup.read_text(encoding="utf-8") == "version-1\n"
    assert second_backup.read_text(encoding="utf-8") == "version-2\n"
    assert len(list((tmp_path / "backups").iterdir())) == 2
