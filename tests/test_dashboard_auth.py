import pytest

from soundtrack_engine.dashboard import auth


@pytest.fixture(autouse=True)
def _dashboard_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", auth.hash_password("correct horse"))
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DASHBOARD_SESSION_DAYS", "30")


def test_verify_password_accepts_correct_password() -> None:
    assert auth.verify_password("correct horse") is True


def test_verify_password_rejects_wrong_password() -> None:
    assert auth.verify_password("wrong") is False


def test_session_token_round_trips() -> None:
    token = auth.create_session_token()
    assert auth.session_token_is_valid(token) is True


def test_session_token_rejects_missing_or_garbage() -> None:
    assert auth.session_token_is_valid(None) is False
    assert auth.session_token_is_valid("") is False
    assert auth.session_token_is_valid("not-a-real-token") is False


def test_session_token_rejects_tampering() -> None:
    token = auth.create_session_token()
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert auth.session_token_is_valid(tampered) is False


def test_session_token_expires(monkeypatch) -> None:
    import time

    monkeypatch.setenv("DASHBOARD_SESSION_DAYS", "0")
    token = auth.create_session_token()
    time.sleep(1.1)  # DASHBOARD_SESSION_DAYS=0 -> max_age=0s, so any elapsed time expires it
    assert auth.session_token_is_valid(token) is False


def test_session_max_age_seconds_reflects_env(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_SESSION_DAYS", "2")
    assert auth.session_max_age_seconds() == 2 * 24 * 60 * 60


def test_missing_config_raises() -> None:
    import os

    del os.environ["DASHBOARD_PASSWORD_HASH"]
    with pytest.raises(auth.AuthNotConfiguredError):
        auth.verify_password("anything")
