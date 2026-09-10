import random

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.generator import generate_progression, generate_stage, generate_stage_tracks
from soundtrack_engine.models import Track


def _tracks(*durations_ms: int) -> list[Track]:
    return [Track(uri=f"spotify:track:{i}", duration_ms=ms) for i, ms in enumerate(durations_ms)]


def _tracks_with_artists(*artist_ids: str, duration_ms: int = 60_000) -> list[Track]:
    return [
        Track(uri=f"spotify:track:{i}", duration_ms=duration_ms, artist_id=artist_id)
        for i, artist_id in enumerate(artist_ids)
    ]


def _adjacent_same_artist_count(tracks: list[Track]) -> int:
    return sum(1 for a, b in zip(tracks, tracks[1:]) if a.artist_id == b.artist_id)


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


def test_generate_stage_tracks_avoids_adjacent_same_artist_when_feasible() -> None:
    # 2 tracks each from 3 different artists, 1 min each; target forces all 6 in.
    # Max group size (2) is well within what a no-adjacent-repeat order allows.
    pool = _tracks_with_artists("A", "A", "B", "B", "C", "C")

    selected = generate_stage_tracks(pool, target_minutes=6, tolerance_minutes=0.5)

    assert len(selected) == 6
    assert _adjacent_same_artist_count(selected) == 0


def test_generate_stage_tracks_minimizes_adjacent_repeats_when_infeasible() -> None:
    # One artist (A) has 4 of 6 tracks — more than half, so at least one adjacent
    # repeat is mathematically unavoidable. The algorithm should still hold that
    # to the theoretical minimum (1), not let them clump together.
    pool = _tracks_with_artists("A", "A", "A", "A", "B", "C")

    selected = generate_stage_tracks(pool, target_minutes=6, tolerance_minutes=0.5)

    assert len(selected) == 6
    assert _adjacent_same_artist_count(selected) == 1


def test_generate_stage_tracks_diversify_does_not_change_which_tracks_are_picked() -> None:
    pool = _tracks_with_artists("A", "A", "B", "B", "C", "C")

    selected = generate_stage_tracks(pool, target_minutes=6, tolerance_minutes=0.5)

    assert {t.uri for t in selected} == {t.uri for t in pool}


def test_generate_stage_open_ended_avoids_adjacent_same_artist_when_feasible() -> None:
    pool = _tracks_with_artists("A", "A", "B", "B", "C", "C")
    stage = Stage(id="reading", name="Reading / journaling", open_ended=True)

    result = generate_stage(stage, pool, tolerance_minutes=2, rng=random.Random(7))

    assert {t.uri for t in result} == {t.uri for t in pool}
    assert _adjacent_same_artist_count(result) == 0
