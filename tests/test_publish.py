from datetime import datetime, timezone
from random import Random

from soundtrack_engine.config import Config, Progression, Stage
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.models import Track
from soundtrack_engine.publish import rebuild_progression

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


class FakeSpotifyClient:
    def __init__(self, pools: dict[str, list[Track]]) -> None:
        self._pools = pools
        self.replaced: dict[str, list[str]] = {}

    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        return self._pools[playlist_id]

    def replace_playlist_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        self.replaced[playlist_id] = track_uris


def _config() -> Config:
    stages = [
        Stage(id="a", name="A", source_playlist_id="pool-a", target_minutes=5),
        Stage(id="b", name="B", source_playlist_id="pool-b", target_minutes=5),
    ]
    progression = Progression(
        output_playlist_name="Test Output", output_playlist_id="output-1", stages=stages
    )
    return Config(progressions={"morning": progression})


def _tracks(prefix: str, *durations_ms: int) -> list[Track]:
    return [Track(uri=f"spotify:track:{prefix}{i}", duration_ms=ms) for i, ms in enumerate(durations_ms)]


def test_rebuild_progression_writes_concatenated_tracks_to_output_playlist() -> None:
    config = _config()
    # Single-track pools sized to exactly match each stage's target, so the pick is forced.
    pools = {
        "pool-a": _tracks("a", 5 * 60_000),
        "pool-b": _tracks("b", 5 * 60_000),
    }
    client = FakeSpotifyClient(pools)
    history = PlayHistory(db_path=":memory:")

    result = rebuild_progression("morning", config, client, history, now=NOW)

    assert [t.uri for t in result] == ["spotify:track:a0", "spotify:track:b0"]
    assert client.replaced["output-1"] == ["spotify:track:a0", "spotify:track:b0"]


def test_rebuild_progression_records_history_per_stage() -> None:
    config = _config()
    pools = {
        "pool-a": _tracks("a", 5 * 60_000),
        "pool-b": _tracks("b", 5 * 60_000),
    }
    client = FakeSpotifyClient(pools)
    history = PlayHistory(db_path=":memory:")

    rebuild_progression("morning", config, client, history, now=NOW)

    # The track just used in stage "a" should now show reduced weight for stage "a"...
    weights_a = history.weights_for("morning", "a", pools["pool-a"], no_repeat_days=15, now=NOW)
    assert weights_a[0] < 1.0
    # ...but stage "b"'s history is untouched by what played in stage "a".
    weights_b_unaffected = history.weights_for("morning", "b", pools["pool-a"], no_repeat_days=15, now=NOW)
    assert weights_b_unaffected[0] == 1.0


def test_rebuild_progression_favors_less_recently_played_tracks_on_repeat_runs() -> None:
    config = _config()
    # Two candidates per stage so history-driven weighting has something to influence.
    pools = {
        "pool-a": _tracks("a", 5 * 60_000, 5 * 60_000),
        "pool-b": _tracks("b", 5 * 60_000, 5 * 60_000),
    }
    client = FakeSpotifyClient(pools)
    history = PlayHistory(db_path=":memory:")

    # Weighted-random, not guaranteed — seeded for a reproducible test run rather
    # than relying on the ~99:1 odds (1.0 vs the 0.01 floor weight) to always land
    # the same way.
    first_run = rebuild_progression("morning", config, client, history, rng=Random(1), now=NOW)
    first_pick_uri = next(t.uri for t in first_run if t.uri.startswith("spotify:track:a"))

    # Immediately rebuild again: the just-used track for stage "a" should be heavily
    # deprioritized, so with only two candidates the other one should win instead.
    second_run = rebuild_progression("morning", config, client, history, rng=Random(2), now=NOW)
    second_pick_uri = next(t.uri for t in second_run if t.uri.startswith("spotify:track:a"))

    assert second_pick_uri != first_pick_uri
