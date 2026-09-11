from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from soundtrack_engine.dashboard import auth
from soundtrack_engine.dashboard.app import create_app
from soundtrack_engine.dashboard.dependencies import (
    get_config_path,
    get_history,
    get_spotify_client,
)
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.models import Track

PASSWORD = "correct horse battery staple"


class FakeSpotifyClient:
    def __init__(self, pools: dict[str, list[Track]]) -> None:
        self._pools = pools
        self.replaced: dict[str, list[str]] = {}
        self.fail = False

    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        if self.fail:
            raise RuntimeError("Not logged in yet — run `soundtrack-engine login` first.")
        return self._pools.get(playlist_id, [])

    def replace_playlist_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        self.replaced[playlist_id] = track_uris


def _write_config(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "progressions": {
                    "morning": {
                        "output_playlist_name": "Today's Ascent",
                        "output_playlist_id": "out-morning",
                        "stages": [
                            {
                                "id": "wake",
                                "name": "Wake",
                                "source_playlist_id": "pool-wake",
                                "target_minutes": 15,
                            },
                            {
                                "id": "groove",
                                "name": "Groove",
                                "source_playlist_id": "pool-groove",
                                "target_minutes": 11,
                            },
                            {
                                "id": "fun",
                                "name": "Full send",
                                "source_playlist_id": "pool-fun",
                                "open_ended": True,
                            },
                        ],
                    },
                    "night": {
                        "output_playlist_name": "Tonight's Descent",
                        "output_playlist_id": "out-night",
                        "stages": [
                            {
                                "id": "soft",
                                "name": "Soft landing",
                                "source_playlist_id": "pool-soft",
                                "target_minutes": 10,
                            },
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", auth.hash_password(PASSWORD))
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DASHBOARD_COOKIE_SECURE", "false")

    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    fake_client = FakeSpotifyClient(
        {
            "pool-wake": [Track(uri="spotify:track:w1", duration_ms=15 * 60_000, name="Song W", artists=["Artist W"])],
            "pool-groove": [Track(uri="spotify:track:g1", duration_ms=11 * 60_000, name="Song G", artists=["Artist G"])],
            "pool-fun": [Track(uri="spotify:track:f1", duration_ms=3 * 60_000, name="Song F", artists=["Artist F"])],
        }
    )

    app = create_app()
    app.dependency_overrides[get_config_path] = lambda: config_path
    app.dependency_overrides[get_spotify_client] = lambda: fake_client
    app.dependency_overrides[get_history] = lambda: PlayHistory(db_path=":memory:")

    client = TestClient(app)
    return client, config_path, fake_client


def _login(client: TestClient) -> None:
    response = client.post("/login", data={"password": PASSWORD})
    assert response.status_code == 200  # TestClient follows the 303 by default
    assert "text/html" in response.headers["content-type"]


def test_login_wrong_password_redirects_with_error(dashboard) -> None:
    client, _, _ = dashboard
    response = client.post(
        "/login", data={"password": "wrong"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=Incorrect+password"
    assert auth.SESSION_COOKIE_NAME not in response.cookies


def test_login_correct_password_sets_cookie_and_redirects_home(dashboard) -> None:
    client, _, _ = dashboard
    response = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert auth.SESSION_COOKIE_NAME in response.cookies


def test_dashboard_page_requires_auth(dashboard) -> None:
    client, _, _ = dashboard
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_page_renders_stages_when_authenticated(dashboard) -> None:
    client, _, _ = dashboard
    _login(client)
    response = client.get("/")
    assert response.status_code == 200
    assert "Wake" in response.text
    assert "Groove" in response.text
    assert "Descent" in response.text  # the other-progression toggle link (Night -> Descent)


def test_save_config_updates_yaml_on_disk(dashboard) -> None:
    client, config_path, _ = dashboard
    _login(client)

    response = client.post(
        "/api/config/morning",
        data={
            "minutes__wake": "20",
            "minutes__groove": "9",
            "infinite__fun": "on",
        },
    )

    assert response.status_code == 200
    assert "Saved." in response.text

    saved = yaml.safe_load(config_path.read_text())
    stages = {s["id"]: s for s in saved["progressions"]["morning"]["stages"]}
    assert stages["wake"]["target_minutes"] == 20
    assert stages["groove"]["target_minutes"] == 9
    assert stages["fun"]["open_ended"] is True


def test_save_config_rejects_infinite_on_middle_stage(dashboard) -> None:
    client, config_path, _ = dashboard
    _login(client)
    original = config_path.read_text()

    response = client.post(
        "/api/config/morning",
        data={
            "minutes__wake": "15",
            "infinite__groove": "on",
            "infinite__fun": "on",
        },
    )

    assert response.status_code == 422
    assert "may not be open-ended" in response.text
    assert config_path.read_text() == original  # nothing written on failure


def test_generate_writes_output_playlist_and_shows_track_table(dashboard) -> None:
    client, _, fake_client = dashboard
    _login(client)

    response = client.post("/api/generate/morning")

    assert response.status_code == 200
    assert "Generated Ascent" in response.text
    assert "Song W" in response.text
    assert "Artist W" in response.text
    assert "Wake" in response.text  # bucket/stage name column
    assert fake_client.replaced["out-morning"]  # published to Spotify


def test_dashboard_page_shows_no_playlist_message_when_never_generated(dashboard) -> None:
    client, _, _ = dashboard
    _login(client)

    response = client.get("/")

    assert response.status_code == 200
    assert "No playlist generated yet" in response.text


def test_dashboard_page_shows_current_live_playlist(dashboard) -> None:
    client, _, fake_client = dashboard
    shared_history = PlayHistory(db_path=":memory:")
    client.app.dependency_overrides[get_history] = lambda: shared_history

    live_track = Track(uri="spotify:track:w1", duration_ms=15 * 60_000, name="Song W", artists=["Artist W"])
    fake_client._pools["out-morning"] = [live_track]
    shared_history.record_generation("morning", "wake", [live_track])

    _login(client)
    response = client.get("/")

    assert response.status_code == 200
    assert "Current Ascent playlist" in response.text
    assert "Song W" in response.text
    assert "Wake" in response.text


def test_dashboard_page_reports_spotify_failure_without_crashing(dashboard) -> None:
    client, _, fake_client = dashboard
    fake_client.fail = True
    _login(client)

    response = client.get("/")

    assert response.status_code == 200
    assert "load the current Ascent playlist" in response.text  # apostrophe gets HTML-escaped
    assert "Wake" in response.text  # the rest of the page (stage editor) still renders


def test_generate_reports_spotify_failure_without_touching_config(dashboard) -> None:
    client, config_path, fake_client = dashboard
    _login(client)
    fake_client.fail = True
    original = config_path.read_text()

    response = client.post("/api/generate/morning")

    assert response.status_code == 502
    assert "failed" in response.text.lower()
    assert config_path.read_text() == original


def test_generate_requires_auth(dashboard) -> None:
    client, _, _ = dashboard
    response = client.post("/api/generate/morning", follow_redirects=False)
    assert response.status_code == 303


def test_logout_clears_cookie(dashboard) -> None:
    client, _, _ = dashboard
    _login(client)
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303

    # Session cookie no longer grants access.
    client.cookies.clear()
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
