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
            {"track": {"uri": "spotify:track:1", "duration_ms": 100, "is_local": False}},
            {"track": {"uri": "spotify:track:2", "duration_ms": 200, "is_local": True}},
        ],
        "next": "https://api.spotify.com/v1/playlists/x/tracks?offset=100",
    }
    page_two = MagicMock()
    page_two.raise_for_status.return_value = None
    page_two.json.return_value = {
        "items": [
            {"track": {"uri": "spotify:track:3", "duration_ms": 300, "is_local": False}},
            {"track": None},
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
