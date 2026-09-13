"""Ties Phases 2-4 together into one rebuild: fetch each stage's pool, weight it by
play history, generate, write the result to the output playlist, and record what
was used. The "automatic, on a schedule" half of Phase 5 (Publishing) — running
this via a scheduler on a host somewhere — isn't built yet; this is the on-demand
building block that will sit underneath it.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from random import Random

from soundtrack_engine.config import Config
from soundtrack_engine.generator import generate_stage
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.logging_setup import get_logger
from soundtrack_engine.models import StageResult
from soundtrack_engine.spotify_client import SpotifyClient

logger = get_logger(__name__)

# Used by current_playlist() when a live track can't be matched to any known
# stage (e.g. added by hand in Spotify, or generated before that stage existed).
UNKNOWN_STAGE_ID = "__unknown__"
UNKNOWN_STAGE_NAME = "Unknown"


def rebuild_progression(
    progression_key: str,
    config: Config,
    client: SpotifyClient,
    history: PlayHistory,
    rng: Random | None = None,
    now: datetime | None = None,
) -> list[StageResult]:
    """Rebuild one progression (e.g. "morning") end to end. Returns each stage's
    generated tracks, in stage order, tagged with which stage they came from — the
    same order written to the output playlist.
    """
    # Computed once and shared across every stage's history record below (rather
    # than each stage call defaulting its own "now") so current_playlist() can
    # identify "everything from this one run" as a single batch sharing one
    # timestamp, regardless of how many stages the progression has.
    now = now or datetime.now(timezone.utc)
    progression = config.progressions[progression_key]
    results: list[StageResult] = []

    for stage in progression.stages:
        pool = client.fetch_playlist_tracks(stage.source_playlist_id)
        weights = history.weights_for(
            progression_key, stage.id, pool, config.generator.no_repeat_days, now=now
        )
        stage_tracks = generate_stage(
            stage, pool, config.generator.duration_tolerance_minutes, weights, rng
        )
        logger.info("%s/%s: %d tracks from a pool of %d", progression_key, stage.id, len(stage_tracks), len(pool))

        history.record_generation(progression_key, stage.id, stage_tracks, when=now)
        results.append(StageResult(stage_id=stage.id, stage_name=stage.name, tracks=stage_tracks))

    all_uris = [t.uri for result in results for t in result.tracks]
    client.replace_playlist_tracks(progression.output_playlist_id, all_uris)
    return results


def current_playlist(
    progression_key: str,
    config: Config,
    client: SpotifyClient,
    history: PlayHistory,
) -> list[StageResult]:
    """Read back what's actually live in a progression's output playlist right now,
    grouped by stage — a read-only counterpart to rebuild_progression: no picks, no
    writes, no history changes. Spotify doesn't track stage membership itself, so
    it's reattached from the most recent generation run's history, matched
    positionally rather than by uri alone: a song briefly present in two stages'
    pools at once (e.g. an earlier stage and the open-ended final stage, before
    being removed from one) gets recorded under both, so a plain uri-keyed lookup
    can't tell its two physical copies apart and would mislabel one of them. A
    track with no recorded history at all (hand-added directly in Spotify) falls
    back to an "Unknown" stage. Tracks are grouped into consecutive runs by stage
    in the playlist's actual live order, so a playlist that was hand-reordered in
    Spotify shows that honestly rather than being forced back into its
    originally-generated grouping.
    """
    progression = config.progressions[progression_key]
    live_tracks = client.fetch_playlist_tracks(progression.output_playlist_id)
    stage_names = {stage.id: stage.name for stage in progression.stages}

    stage_queue: dict[str, list[str]] = defaultdict(list)
    for uri, stage_id in history.latest_run_stage_sequence(progression_key):
        stage_queue[uri].append(stage_id)

    last_known_stage: dict[str, str] = {}
    results: list[StageResult] = []
    for track in live_tracks:
        queue = stage_queue.get(track.uri)
        if queue:
            stage_id = queue.pop(0)
            last_known_stage[track.uri] = stage_id
        else:
            # Queue exhausted (or never had one): a hand-reordered duplicate of a
            # track already matched above, or a track with no run recorded at all.
            stage_id = last_known_stage.get(track.uri, UNKNOWN_STAGE_ID)
        stage_name = stage_names.get(stage_id, UNKNOWN_STAGE_NAME)
        if results and results[-1].stage_id == stage_id:
            results[-1].tracks.append(track)
        else:
            results.append(StageResult(stage_id=stage_id, stage_name=stage_name, tracks=[track]))

    return results
