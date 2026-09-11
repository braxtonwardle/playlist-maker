"""Duration-based playlist generation from stage pools.

Per the spec: keep weighted-randomly picking songs from a stage's pool until its
duration is close to `target_minutes` (within `duration_tolerance_minutes`); near
the end, switch to picking whichever remaining track best closes the gap rather
than picking purely at random. `weights` defaults to uniform — Phase 4 will pass
recency-based weights (favoring songs not heard recently) without this module
changing.

Whichever tracks get picked, their order within a stage is then spread out by
primary artist (`_diversify_by_artist`) so a pool with several songs by the same
artist doesn't cluster them back-to-back — this only reorders a stage's own picks,
never moves a track across a stage boundary, so the mood-arc ordering stays intact.
"""

from __future__ import annotations

import heapq
import random
from collections import defaultdict

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.logging_setup import get_logger
from soundtrack_engine.models import Track

logger = get_logger(__name__)

_MS_PER_MINUTE = 60_000


def _diversify_by_artist(tracks: list[Track], rng: random.Random) -> list[Track]:
    """Reorder `tracks` to keep same-artist tracks from landing back-to-back, as
    much as the pool's composition allows (if one artist is more than half the
    list, at least one adjacent repeat is unavoidable — this still minimizes it).
    Which tracks are in the list doesn't change, only their order.
    """
    groups: dict[str, list[Track]] = defaultdict(list)
    for track in tracks:
        groups[track.artist_id].append(track)
    for group in groups.values():
        rng.shuffle(group)

    # Max-heap (by remaining count) of artists still having tracks left to place.
    heap = [(-len(group), rng.random(), artist_id) for artist_id, group in groups.items()]
    heapq.heapify(heap)

    result: list[Track] = []
    held: tuple[int, float, str] | None = None  # the artist just placed, kept out
    # of the heap for one round so it can't be picked again immediately.

    while heap or held is not None:
        if not heap:
            # Only the held-back artist has anything left; no alternative exists.
            neg_count, tiebreak, artist_id = held
            held = None
        else:
            neg_count, tiebreak, artist_id = heapq.heappop(heap)
            if held is not None:
                heapq.heappush(heap, held)
                held = None

        result.append(groups[artist_id].pop())
        neg_count += 1  # one fewer remaining for this artist

        if neg_count < 0:
            held = (neg_count, rng.random(), artist_id)

    return result


def _weighted_pop(rng: random.Random, tracks: list[Track], weights: list[float]) -> Track:
    """Remove and return one track from `tracks`, chosen with probability proportional
    to the matching entry in `weights` (falling back to uniform if all weights are 0).
    Mutates both lists in place, keeping them aligned.
    """
    total = sum(weights)
    if total <= 0:
        index = rng.randrange(len(tracks))
    else:
        target = rng.uniform(0, total)
        cumulative = 0.0
        index = len(tracks) - 1  # float rounding fallback: last item
        for i, weight in enumerate(weights):
            cumulative += weight
            if cumulative >= target:
                index = i
                break

    weights.pop(index)
    return tracks.pop(index)


def generate_stage_tracks(
    pool: list[Track],
    target_minutes: float,
    tolerance_minutes: float,
    weights: list[float] | None = None,
    rng: random.Random | None = None,
) -> list[Track]:
    """Pick tracks from `pool` whose total duration lands near `target_minutes`."""
    if rng is None:
        rng = random.Random()

    remaining_tracks = list(pool)
    remaining_weights = list(weights) if weights is not None else [1.0] * len(pool)

    target_ms = round(target_minutes * _MS_PER_MINUTE)
    tolerance_ms = round(tolerance_minutes * _MS_PER_MINUTE)
    lower_bound_ms = target_ms - tolerance_ms
    upper_bound_ms = target_ms + tolerance_ms

    selected: list[Track] = []
    total_ms = 0

    # Phase 1: weighted-random picks while clearly short of the target.
    while remaining_tracks and total_ms < lower_bound_ms:
        track = _weighted_pop(rng, remaining_tracks, remaining_weights)
        selected.append(track)
        total_ms += track.duration_ms

    # Phase 2: close to target — greedily add whichever remaining track best closes
    # the gap, stopping once we're in tolerance or nothing left would help.
    while remaining_tracks and not (lower_bound_ms <= total_ms <= upper_bound_ms):
        best_index = min(
            range(len(remaining_tracks)),
            key=lambda i: abs(total_ms + remaining_tracks[i].duration_ms - target_ms),
        )
        best_track = remaining_tracks[best_index]
        if total_ms >= lower_bound_ms and abs(total_ms + best_track.duration_ms - target_ms) >= abs(
            total_ms - target_ms
        ):
            break  # already in the lower half of tolerance; adding more would only overshoot worse

        remaining_weights.pop(best_index)
        remaining_tracks.pop(best_index)
        selected.append(best_track)
        total_ms += best_track.duration_ms

    if not (lower_bound_ms <= total_ms <= upper_bound_ms):
        logger.warning(
            "stage target not reached: got %.1f min, wanted %.1f +/- %.1f min (pool exhausted)",
            total_ms / _MS_PER_MINUTE,
            target_minutes,
            tolerance_minutes,
        )

    return _diversify_by_artist(selected, rng)


def generate_stage(
    stage: Stage,
    pool: list[Track],
    tolerance_minutes: float,
    weights: list[float] | None = None,
    rng: random.Random | None = None,
) -> list[Track]:
    """Generate one stage's tracks: the whole pool shuffled if open-ended, else a
    duration-targeted selection.
    """
    if rng is None:
        rng = random.Random()

    if stage.open_ended:
        return _diversify_by_artist(list(pool), rng)

    assert stage.target_minutes is not None  # guaranteed by Stage's own validation
    return generate_stage_tracks(pool, stage.target_minutes, tolerance_minutes, weights, rng)


def generate_progression(
    progression: Progression,
    pools_by_stage_id: dict[str, list[Track]],
    tolerance_minutes: float,
    weights_by_stage_id: dict[str, list[float]] | None = None,
    rng: random.Random | None = None,
) -> list[Track]:
    """Generate a full progression: each stage's tracks, concatenated in stage order."""
    if rng is None:
        rng = random.Random()

    tracks: list[Track] = []
    for stage in progression.stages:
        pool = pools_by_stage_id.get(stage.id, [])
        weights = weights_by_stage_id.get(stage.id) if weights_by_stage_id else None
        tracks.extend(generate_stage(stage, pool, tolerance_minutes, weights, rng))

    return tracks
