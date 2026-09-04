import time
from unittest.mock import MagicMock, patch

import pytest

from soundtrack_engine import spotify_auth


def test_client_credentials_missing_raises(monkeypatch) -> None:
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    with pytest.raises(spotify_auth.MissingCredentialsError):
        spotify_auth._client_credentials()


def test_get_access_token_returns_cached_token_when_not_expired(monkeypatch) -> None:
    monkeypatch.setattr(
        spotify_auth,
        "load_tokens",
        lambda: {"access_token": "cached", "refresh_token": "r", "expires_at": time.time() + 999},
    )

    assert spotify_auth.get_access_token() == "cached"


def test_get_access_token_refreshes_when_expired(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setattr(
        spotify_auth,
        "load_tokens",
        lambda: {"access_token": "old", "refresh_token": "r", "expires_at": time.time() - 10},
    )
    saved = {}
    monkeypatch.setattr(spotify_auth, "save_tokens", lambda tokens: saved.update(tokens))

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"access_token": "new", "expires_in": 3600}

    with patch("soundtrack_engine.spotify_auth.requests.post", return_value=mock_response) as mock_post:
        token = spotify_auth.get_access_token()

    assert token == "new"
    assert saved["access_token"] == "new"
    assert saved["refresh_token"] == "r"  # kept, since the refresh response omitted one
    mock_post.assert_called_once()


def test_get_access_token_raises_if_never_logged_in(monkeypatch) -> None:
    monkeypatch.setattr(spotify_auth, "load_tokens", lambda: None)

    with pytest.raises(RuntimeError):
        spotify_auth.get_access_token()
