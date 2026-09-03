from pathlib import Path

import pytest
from pydantic import ValidationError

from soundtrack_engine.config import Config, Progression, Stage, load_config

EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.example.yaml"


def test_load_example_config() -> None:
    config = load_config(EXAMPLE_CONFIG_PATH)

    assert config.no_repeat_days == 15
    assert set(config.progressions) == {"morning", "night"}
    assert len(config.progressions["morning"].stages) == 5
    assert len(config.progressions["night"].stages) == 5


def test_example_config_stage_names_and_order() -> None:
    config = load_config(EXAMPLE_CONFIG_PATH)

    morning_names = [stage.name for stage in config.progressions["morning"].stages]
    assert morning_names == [
        "Wake / Cinematic",
        "Groove / Getting moving",
        "Warm / Easy",
        "Building energy",
        "Full send / Fun",
    ]

    night_names = [stage.name for stage in config.progressions["night"].stages]
    assert night_names[-1] == "Reading / journaling"


def test_night_reading_stage_is_open_ended_with_no_duration() -> None:
    config = load_config(EXAMPLE_CONFIG_PATH)

    reading_stage = config.progressions["night"].stages[-1]
    assert reading_stage.open_ended is True
    assert reading_stage.target_minutes is None


def test_load_config_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("does/not/exist.yaml")


def test_stage_requires_duration_unless_open_ended() -> None:
    with pytest.raises(ValidationError):
        Stage(name="No duration, not open-ended")


def test_stage_open_ended_rejects_duration() -> None:
    with pytest.raises(ValidationError):
        Stage(name="Both set", open_ended=True, target_minutes=10)


def test_stage_rejects_non_positive_duration() -> None:
    with pytest.raises(ValidationError):
        Stage(name="Zero minutes", target_minutes=0)


def test_progression_requires_at_least_one_stage() -> None:
    with pytest.raises(ValidationError):
        Progression(output_playlist_name="Empty", stages=[])


def test_config_requires_positive_no_repeat_days() -> None:
    with pytest.raises(ValidationError):
        Config(
            no_repeat_days=0,
            progressions={
                "morning": Progression(
                    output_playlist_name="Today's Morning",
                    stages=[Stage(name="Wake", target_minutes=8)],
                )
            },
        )


def test_config_requires_at_least_one_progression() -> None:
    with pytest.raises(ValidationError):
        Config(progressions={})
