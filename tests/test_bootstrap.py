from soundtrack_engine.bootstrap import bootstrap_playlists
from soundtrack_engine.config import Config, Progression, Stage


class FakePlaylistCreator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._next_id = 1

    def create_playlist(self, user_id: str, name: str, description: str = "") -> str:
        self.calls.append((user_id, name, description))
        playlist_id = f"created-{self._next_id}"
        self._next_id += 1
        return playlist_id


def _config() -> Config:
    stages = [
        Stage(id="wake", name="Wake", source_playlist_id="", target_minutes=8),
        Stage(id="groove", name="Groove", source_playlist_id="existing-source", target_minutes=11),
    ]
    progression = Progression(output_playlist_name="Today's Morning", output_playlist_id="", stages=stages)
    return Config(progressions={"morning": progression})


def test_bootstrap_creates_missing_playlists_and_skips_existing() -> None:
    config = _config()
    client = FakePlaylistCreator()

    created = bootstrap_playlists(config, client, user_id="user1")

    assert len(created) == 2
    assert len(client.calls) == 2
    morning = config.progressions["morning"]
    assert morning.output_playlist_id == "created-1"
    assert morning.stages[0].source_playlist_id == "created-2"
    assert morning.stages[1].source_playlist_id == "existing-source"  # untouched


def test_bootstrap_is_a_noop_when_everything_already_has_ids() -> None:
    config = _config()
    config.progressions["morning"].output_playlist_id = "existing-output"
    config.progressions["morning"].stages[0].source_playlist_id = "existing-wake"

    client = FakePlaylistCreator()
    created = bootstrap_playlists(config, client, user_id="user1")

    assert created == []
    assert client.calls == []
