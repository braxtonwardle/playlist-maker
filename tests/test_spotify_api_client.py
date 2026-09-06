from unittest.mock import MagicMock, patch

import pytest

from soundtrack_engine.models import Track
from soundtrack_engine.spotify_api_client import MAX_TRACKS_PER_REPLACE_REQUEST, SpotifyApiClient


def _client() -> SpotifyApiClient:
    return SpotifyApiClient(access_token_provider=lambda: "fake-token")


def test_fetch_playlist_tracks_paginates_and_skips_local_or_missing_tracks() -> None:
    page_one = MagicMock()
    page_one.raise_for_status.return_value = None
    page_one.json.return_value = {
        "items": [
            {"item": {"uri": "spotify:track:1", "duration_ms": 100, "is_local": False}},
            {"item": {"uri": "spotify:track:2", "duration_ms": 200, "is_local": True}},
        ],
        "next": "https://api.spotify.com/v1/playlists/x/items?offset=100",
    }
    page_two = MagicMock()
    page_two.raise_for_status.return_value = None
    page_two.json.return_value = {
        "items": [
            {"item": {"uri": "spotify:track:3", "duration_ms": 300, "is_local": False}},
            {"item": None},
        ],
        "next": None,
    }

    with patch(
        "soundtrack_engine.spotify_api_client.requests.get",
        side_effect=[page_one, page_two],
    ) as mock_get:
        tracks = _client().fetch_playlist_tracks("playlist123")

    assert tracks == [
        Track(uri="spotify:track:1", duration_ms=100),
        Track(uri="spotify:track:3", duration_ms=300),
    ]
    assert mock_get.call_count == 2


def test_replace_playlist_tracks_sends_uris_as_json() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None

    with patch(
        "soundtrack_engine.spotify_api_client.requests.put", return_value=response
    ) as mock_put:
        _client().replace_playlist_tracks("playlist123", ["spotify:track:1", "spotify:track:2"])

    mock_put.assert_called_once()
    assert mock_put.call_args.kwargs["json"] == {
        "uris": ["spotify:track:1", "spotify:track:2"]
    }


def test_replace_playlist_tracks_rejects_too_many_uris() -> None:
    too_many = [f"spotify:track:{i}" for i in range(MAX_TRACKS_PER_REPLACE_REQUEST + 1)]

    with pytest.raises(ValueError):
        _client().replace_playlist_tracks("playlist123", too_many)


def test_get_current_user_id_returns_id() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"id": "user123", "display_name": "Someone"}

    with patch("soundtrack_engine.spotify_api_client.requests.get", return_value=response):
        assert _client().get_current_user_id() == "user123"


def test_create_playlist_returns_new_id_and_sends_expected_payload() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"id": "new-playlist-id"}

    with patch(
        "soundtrack_engine.spotify_api_client.requests.post", return_value=response
    ) as mock_post:
        playlist_id = _client().create_playlist("user123", "My Playlist", description="desc")

    assert playlist_id == "new-playlist-id"
    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "https://api.spotify.com/v1/users/user123/playlists"
    assert mock_post.call_args.kwargs["json"] == {
        "name": "My Playlist",
        "description": "desc",
        "public": False,
    }


def test_get_playlist_name_returns_name() -> None:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"name": "Wake / Cinematic"}

    with patch("soundtrack_engine.spotify_api_client.requests.get", return_value=response):
        assert _client().get_playlist_name("playlist123") == "Wake / Cinematic"
