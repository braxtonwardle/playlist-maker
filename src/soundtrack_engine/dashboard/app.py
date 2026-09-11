"""FastAPI entry point: `uvicorn soundtrack_engine.dashboard.app:app`."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from soundtrack_engine.dashboard.routes import router
from soundtrack_engine.dashboard.security import register_auth_redirect
from soundtrack_engine.logging_setup import configure_logging

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    # Secrets (.env — Spotify credentials, dashboard password hash, session signing
    # key) load once here, at process startup, and are then read from the process
    # environment per-request — deliberately NOT re-read from disk per-request.
    # Rotating a secret should require a restart: that makes the change atomic
    # (every request sees either all-old or all-new secrets, never a torn mix from
    # catching .env mid-edit) and gives rotation a visible, auditable moment in the
    # systemd journal instead of silently taking effect on the next request.
    # Config (config.yaml), by contrast, IS re-read fresh on every request — see
    # dependencies.py's get_config() — since the dashboard's own Save needs to take
    # effect immediately without a restart.
    load_dotenv(override=True)
    configure_logging()

    app = FastAPI(title="Playlist Dashboard", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(router)
    register_auth_redirect(app)
    return app


app = create_app()
