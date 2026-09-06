"""Duration-based playlist generation from stage pools.

Per the spec: keep weighted-randomly picking songs from a stage's pool until its
duration is close to `target_minutes` (within `duration_tolerance_minutes`); near
the end, switch to picking whichever remaining track best closes the gap rather
than picking purely at random. `weights` defaults to uniform — Phase 4 will pass
recency-based weights (favoring songs not heard recently) without this module
changing.
"""

from __future__ import annotations

import random

from soundtrack_engine.config import Progression, Stage
from soundtrack_engine.logging_setup import get_logger
from soundtrack_engine.models import Track

logger = get_logger(__name__)

_MS_PER_MINUTE = 60_000


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

    return selected


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
        shuffled = list(pool)
        rng.shuffle(shuffled)
        return shuffled

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
