import random

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.generator import generate_progression, generate_stage, generate_stage_tracks
from soundtrack_engine.models import Track


def _tracks(*durations_ms: int) -> list[Track]:
    return [Track(uri=f"spotify:track:{i}", duration_ms=ms) for i, ms in enumerate(durations_ms)]


def test_generate_stage_tracks_hits_target_with_uniform_pool() -> None:
    # Six 4-minute tracks; target 12 min +/- 2 min lands exactly on three tracks (12 min),
    # regardless of which three get picked — makes this deterministic without seeding rng.
    pool = _tracks(*([4 * 60_000] * 6))

    selected = generate_stage_tracks(pool, target_minutes=12, tolerance_minutes=2)

    assert len(selected) == 3
    assert sum(t.duration_ms for t in selected) == 12 * 60_000


def test_generate_stage_tracks_selects_only_from_pool_with_no_duplicates() -> None:
    pool = _tracks(60_000, 120_000, 90_000, 200_000, 150_000, 80_000, 300_000, 45_000)
    rng = random.Random(42)

    selected = generate_stage_tracks(pool, target_minutes=10, tolerance_minutes=3, rng=rng)

    uris = [t.uri for t in selected]
    assert len(uris) == len(set(uris))
    assert set(uris) <= {t.uri for t in pool}


def test_generate_stage_tracks_uses_entire_pool_when_too_small_for_target(caplog) -> None:
    pool = _tracks(60_000)  # 1 minute, nowhere near a 20-minute target

    with caplog.at_level("WARNING"):
        selected = generate_stage_tracks(pool, target_minutes=20, tolerance_minutes=2)

    assert selected == pool
    assert "stage target not reached" in caplog.text


def test_generate_stage_open_ended_returns_entire_pool_shuffled() -> None:
    pool = _tracks(*(i * 1000 for i in range(1, 11)))
    stage = Stage(id="reading", name="Reading / journaling", open_ended=True)

    result = generate_stage(stage, pool, tolerance_minutes=2, rng=random.Random(7))

    assert {t.uri for t in result} == {t.uri for t in pool}
    assert len(result) == len(pool)


def test_generate_progression_concatenates_stages_in_order() -> None:
    # Single-track pools sized to exactly match each stage's target within a tight
    # tolerance, so each stage's pick is forced regardless of rng.
    stage_a = Stage(id="a", name="A", target_minutes=5)
    stage_b = Stage(id="b", name="B", target_minutes=8)
    progression = Progression(output_playlist_name="Test", stages=[stage_a, stage_b])

    track_a = Track(uri="spotify:track:a", duration_ms=5 * 60_000)
    track_b = Track(uri="spotify:track:b", duration_ms=8 * 60_000)
    pools = {"a": [track_a], "b": [track_b]}

    result = generate_progression(progression, pools, tolerance_minutes=1)

    assert [t.uri for t in result] == ["spotify:track:a", "spotify:track:b"]


def test_generate_progression_uses_empty_list_for_stage_with_no_pool_entry() -> None:
    stage = Stage(id="missing", name="Missing", target_minutes=5)
    progression = Progression(output_playlist_name="Test", stages=[stage])

    result = generate_progression(progression, pools_by_stage_id={}, tolerance_minutes=1)

    assert result == []
