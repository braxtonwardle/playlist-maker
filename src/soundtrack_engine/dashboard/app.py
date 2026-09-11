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
    load_dotenv(override=True)
    configure_logging()

    app = FastAPI(title="Playlist Dashboard", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(router)
    register_auth_redirect(app)
    return app


app = create_app()
