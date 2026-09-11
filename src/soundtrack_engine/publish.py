"""Ties Phases 2-4 together into one rebuild: fetch each stage's pool, weight it by
play history, generate, write the result to the output playlist, and record what
was used. The "automatic, on a schedule" half of Phase 5 (Publishing) — running
this via a scheduler on a host somewhere — isn't built yet; this is the on-demand
building block that will sit underneath it.
"""

from __future__ import annotations

from datetime import datetime
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
    it's reattached from the most recent generation history recorded for each
    track; a track with no recorded history falls back to an "Unknown" stage.
    Tracks are grouped into consecutive runs by stage in the playlist's actual
    live order, so a playlist that was hand-reordered in Spotify shows that
    honestly rather than being forced back into its originally-generated grouping.
    """
    progression = config.progressions[progression_key]
    live_tracks = client.fetch_playlist_tracks(progression.output_playlist_id)
    stage_by_uri = history.latest_stage_by_uri(progression_key)
    stage_names = {stage.id: stage.name for stage in progression.stages}

    results: list[StageResult] = []
    for track in live_tracks:
        stage_id = stage_by_uri.get(track.uri, UNKNOWN_STAGE_ID)
        stage_name = stage_names.get(stage_id, UNKNOWN_STAGE_NAME)
        if results and results[-1].stage_id == stage_id:
            results[-1].tracks.append(track)
        else:
            results.append(StageResult(stage_id=stage_id, stage_name=stage_name, tracks=[track]))

    return results
