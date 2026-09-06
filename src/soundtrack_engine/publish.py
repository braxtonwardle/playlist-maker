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
from soundtrack_engine.models import Track
from soundtrack_engine.spotify_client import SpotifyClient

logger = get_logger(__name__)


def rebuild_progression(
    progression_key: str,
    config: Config,
    client: SpotifyClient,
    history: PlayHistory,
    rng: Random | None = None,
    now: datetime | None = None,
) -> list[Track]:
    """Rebuild one progression (e.g. "morning") end to end. Returns the full track
    list written to its output playlist, in order.
    """
    progression = config.progressions[progression_key]
    all_tracks: list[Track] = []

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
        all_tracks.extend(stage_tracks)

    client.replace_playlist_tracks(progression.output_playlist_id, [t.uri for t in all_tracks])
    return all_tracks
