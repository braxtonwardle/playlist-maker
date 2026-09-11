from datetime import datetime, timedelta, timezone

import pytest

from soundtrack_engine.history import PlayHistory
from soundtrack_engine.models import Track

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def _history() -> PlayHistory:
    return PlayHistory(db_path=":memory:")


def test_never_played_track_gets_full_weight() -> None:
    history = _history()
    tracks = [Track(uri="spotify:track:1", duration_ms=200_000)]

    weights = history.weights_for("morning", "wake", tracks, no_repeat_days=15, now=NOW)

    assert weights == [1.0]


def test_track_played_moments_ago_gets_minimum_weight() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW)

    weights = history.weights_for("morning", "wake", [track], no_repeat_days=15, now=NOW)

    assert weights[0] == pytest.approx(0.01, abs=1e-9)


def test_weight_ramps_up_partway_through_the_window() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW - timedelta(days=7.5))

    weights = history.weights_for("morning", "wake", [track], no_repeat_days=15, now=NOW)

    assert 0.4 < weights[0] < 0.6


def test_track_played_past_the_window_gets_full_weight_again() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW - timedelta(days=20))

    weights = history.weights_for("morning", "wake", [track], no_repeat_days=15, now=NOW)

    assert weights == [1.0]


def test_weights_use_most_recent_play_not_first() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW - timedelta(days=20))
    history.record_generation("morning", "wake", [track], when=NOW)  # played again, just now

    weights = history.weights_for("morning", "wake", [track], no_repeat_days=15, now=NOW)

    assert weights[0] == pytest.approx(0.01, abs=1e-9)


def test_weights_are_scoped_by_progression_and_stage() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW)

    # Same track uri, but a different stage and a different progression — unaffected.
    other_stage_weights = history.weights_for("morning", "groove", [track], no_repeat_days=15, now=NOW)
    other_progression_weights = history.weights_for("night", "wake", [track], no_repeat_days=15, now=NOW)

    assert other_stage_weights == [1.0]
    assert other_progression_weights == [1.0]


def test_record_generation_covers_multiple_tracks() -> None:
    history = _history()
    tracks = [
        Track(uri="spotify:track:1", duration_ms=200_000),
        Track(uri="spotify:track:2", duration_ms=180_000),
    ]
    history.record_generation("morning", "wake", tracks, when=NOW)

    weights = history.weights_for("morning", "wake", tracks, no_repeat_days=15, now=NOW)

    assert weights == [pytest.approx(0.01, abs=1e-9), pytest.approx(0.01, abs=1e-9)]


def test_last_generated_at_returns_none_when_never_generated() -> None:
    history = _history()
    assert history.last_generated_at("morning") is None


def test_last_generated_at_returns_most_recent_run_across_stages() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW - timedelta(days=1))
    history.record_generation("morning", "groove", [track], when=NOW)

    assert history.last_generated_at("morning") == NOW


def test_last_generated_at_is_scoped_by_progression() -> None:
    history = _history()
    track = Track(uri="spotify:track:1", duration_ms=200_000)
    history.record_generation("night", "soft_landing", [track], when=NOW)

    assert history.last_generated_at("morning") is None


def test_latest_stage_by_uri_returns_empty_when_never_generated() -> None:
    history = _history()
    assert history.latest_stage_by_uri("morning") == {}


def test_latest_stage_by_uri_maps_each_track_to_its_stage() -> None:
    history = _history()
    track_a = Track(uri="spotify:track:a", duration_ms=200_000)
    track_b = Track(uri="spotify:track:b", duration_ms=200_000)
    history.record_generation("morning", "wake", [track_a], when=NOW)
    history.record_generation("morning", "groove", [track_b], when=NOW)

    assert history.latest_stage_by_uri("morning") == {
        "spotify:track:a": "wake",
        "spotify:track:b": "groove",
    }


def test_latest_stage_by_uri_uses_most_recent_stage_if_track_moved() -> None:
    history = _history()
    track = Track(uri="spotify:track:a", duration_ms=200_000)
    history.record_generation("morning", "wake", [track], when=NOW - timedelta(days=1))
    history.record_generation("morning", "groove", [track], when=NOW)

    assert history.latest_stage_by_uri("morning") == {"spotify:track:a": "groove"}


def test_latest_stage_by_uri_is_scoped_by_progression() -> None:
    history = _history()
    track = Track(uri="spotify:track:a", duration_ms=200_000)
    history.record_generation("night", "soft_landing", [track], when=NOW)

    assert history.latest_stage_by_uri("morning") == {}


def test_context_manager_closes_connection() -> None:
    with PlayHistory(db_path=":memory:") as history:
        history.record_generation("morning", "wake", [], when=NOW)

    with pytest.raises(Exception):
        history._conn.execute("SELECT 1")
