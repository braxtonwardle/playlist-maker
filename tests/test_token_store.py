import json

from soundtrack_engine import token_store


def test_save_and_load_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(token_store, "_TOKEN_PATH", tmp_path / "tokens.json")

    token_store.save_tokens({"access_token": "a", "refresh_token": "b", "expires_at": 123.0})

    assert token_store.load_tokens() == {
        "access_token": "a",
        "refresh_token": "b",
        "expires_at": 123.0,
    }


def test_save_tokens_writes_json(tmp_path, monkeypatch) -> None:
    path = tmp_path / "tokens.json"
    monkeypatch.setattr(token_store, "_TOKEN_PATH", path)

    token_store.save_tokens({"access_token": "a"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"access_token": "a"}


def test_load_tokens_returns_none_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(token_store, "_TOKEN_PATH", tmp_path / "does-not-exist.json")

    assert token_store.load_tokens() is None
