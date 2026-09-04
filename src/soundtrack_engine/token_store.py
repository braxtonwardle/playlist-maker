"""Local storage for Spotify OAuth tokens (access + refresh)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / ".spotify-tokens.json"


def load_tokens() -> dict[str, Any] | None:
    if not _TOKEN_PATH.exists():
        return None
    return json.loads(_TOKEN_PATH.read_text(encoding="utf-8"))


def save_tokens(tokens: dict[str, Any]) -> None:
    _TOKEN_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
