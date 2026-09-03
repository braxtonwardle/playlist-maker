from pathlib import Path

import pytest
from pydantic import ValidationError

from soundtrack_engine.config import Config, GeneratorSettings, Progression, Stage, load_config

EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.example.yaml"


def test_load_example_config() -> None:
    config = load_config(EXAMPLE_CONFIG_PATH)

    assert config.generator.no_repeat_days == 15
    assert config.generator.duration_tolerance_minutes == 2
    assert set(config.progressions) == {"morning", "night"}
    assert len(config.progressions["morning"].stages) == 5
    assert len(config.progressions["night"].stages) == 5


def test_example_config_stage_ids_and_names_in_order() -> None:
    config = load_config(EXAMPLE_CONFIG_PATH)

    morning_stages = config.progressions["morning"].stages
    assert [s.id for s in morning_stages] == [
        "wake_cinematic",
        "groove",
        "warm",
        "building_energy",
        "full_send_fun",
    ]
    assert [s.name for s in morning_stages] == [
        "Wake / Cinematic",
        "Groove / Getting moving",
        "Warm / Easy",
        "Building energy",
        "Full send / Fun",
    ]

    night_stages = config.progressions["night"].stages
    assert night_stages[-1].id == "reading_journaling"
    assert night_stages[-1].name == "Reading / journaling"


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
        Stage(id="wake", name="No duration, not open-ended")


def test_stage_open_ended_rejects_duration() -> None:
    with pytest.raises(ValidationError):
        Stage(id="both_set", name="Both set", open_ended=True, target_minutes=10)


def test_stage_rejects_non_positive_duration() -> None:
    with pytest.raises(ValidationError):
        Stage(id="zero_minutes", name="Zero minutes", target_minutes=0)


def test_stage_rejects_invalid_id() -> None:
    with pytest.raises(ValidationError):
        Stage(id="Not Snake Case!", name="Bad id", target_minutes=5)


def test_progression_requires_at_least_one_stage() -> None:
    with pytest.raises(ValidationError):
        Progression(output_playlist_name="Empty", stages=[])


def test_progression_rejects_duplicate_stage_ids() -> None:
    with pytest.raises(ValidationError):
        Progression(
            output_playlist_name="Dupes",
            stages=[
                Stage(id="wake", name="Wake", target_minutes=8),
                Stage(id="wake", name="Wake Again", target_minutes=8),
            ],
        )


def test_generator_settings_reject_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        GeneratorSettings(no_repeat_days=0)
    with pytest.raises(ValidationError):
        GeneratorSettings(duration_tolerance_minutes=0)


def test_config_requires_at_least_one_progression() -> None:
    with pytest.raises(ValidationError):
        Config(progressions={})
