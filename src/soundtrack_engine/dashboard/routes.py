"""Route handlers for the dashboard: login/logout, the single main page, saving
stage durations, and triggering generation. Kept intentionally small per the
dashboard spec — no analytics, no extra screens, just config edit + generate.
"""

from __future__ import annotations

from pathlib import Path

import requests
import yaml
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from soundtrack_engine.config import Config
from soundtrack_engine.dashboard import auth
from soundtrack_engine.dashboard.config_editing import (
    StageEditNotAllowed,
    StageUpdate,
    apply_stage_updates,
    backup_config,
)
from soundtrack_engine.dashboard.dependencies import (
    get_config,
    get_config_path,
    get_history,
    get_spotify_client,
)
from soundtrack_engine.dashboard.security import require_auth
from soundtrack_engine.dashboard.theme import stage_colors_for
from soundtrack_engine.history import PlayHistory
from soundtrack_engine.publish import current_playlist, rebuild_progression
from soundtrack_engine.spotify_client import SpotifyClient

router = APIRouter()
_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Display labels only — output_playlist_name already reads "Today's Ascent" /
# "Tonight's Descent"; this just carries that naming into the toggle/buttons too.
# The underlying progression keys ("morning"/"night") are unchanged: they're what
# the CLI, cron jobs, and history.db rows key on, so renaming them would break the
# already-deployed cron commands and reset no-repeat history.
PROGRESSION_LABELS = {"morning": "Ascent", "night": "Descent"}


def _progression_label(key: str) -> str:
    return PROGRESSION_LABELS.get(key, key.capitalize())


def _other_progression(config: Config, progression: str) -> str | None:
    others = [key for key in config.progressions if key != progression]
    return others[0] if others else None


def _dashboard_context(request: Request, progression: str, config: Config, history: PlayHistory) -> dict:
    if progression not in config.progressions:
        progression = next(iter(config.progressions))
    other_progression = _other_progression(config, progression)
    stages = config.progressions[progression].stages
    return {
        "request": request,
        "progression": progression,
        "progression_label": _progression_label(progression),
        "other_progression": other_progression,
        "other_progression_label": _progression_label(other_progression) if other_progression else None,
        "stages": stages,
        "stage_colors": stage_colors_for([stage.id for stage in stages]),
        "last_generated": history.last_generated_at(progression),
    }


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login", include_in_schema=False)
def login_submit(password: str = Form(...)) -> RedirectResponse:
    if not auth.verify_password(password):
        return RedirectResponse(
            "/login?error=Incorrect+password", status_code=status.HTTP_303_SEE_OTHER
        )

    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        auth.SESSION_COOKIE_NAME,
        auth.create_session_token(),
        httponly=True,
        secure=auth.cookie_is_secure(),
        samesite="lax",
        max_age=auth.session_max_age_seconds(),
    )
    return response


@router.post("/logout", include_in_schema=False)
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(auth.SESSION_COOKIE_NAME)
    return response


def _live_playlist_view(
    progression: str,
    progression_label: str,
    config: Config,
    client: SpotifyClient,
    history: PlayHistory,
) -> dict:
    """Context for the passive "what's live right now" view shown on page load —
    a plain read of the output playlist, no picks, no writes, no history changes.
    """
    try:
        results = current_playlist(progression, config, client, history)
    except (requests.RequestException, RuntimeError) as error:
        return {"error_message": f"Couldn't load the current {progression_label} playlist: {error}"}
    return {"results": results, "heading": f"Current {progression_label} playlist"}


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
def dashboard_page(
    request: Request,
    progression: str = "morning",
    config: Config = Depends(get_config),
    client: SpotifyClient = Depends(get_spotify_client),
    history: PlayHistory = Depends(get_history),
) -> HTMLResponse:
    context = _dashboard_context(request, progression, config, history)
    context.update(
        _live_playlist_view(context["progression"], context["progression_label"], config, client, history)
    )
    return templates.TemplateResponse(request, "dashboard.html", context)


@router.post(
    "/api/config/{progression}", response_class=HTMLResponse, dependencies=[Depends(require_auth)]
)
async def save_config(
    request: Request,
    progression: str,
    config: Config = Depends(get_config),
    history: PlayHistory = Depends(get_history),
    config_path: Path = Depends(get_config_path),
) -> HTMLResponse:
    if progression not in config.progressions:
        raise HTTPException(status_code=404, detail=f'unknown progression "{progression}"')

    form = await request.form()
    stages = config.progressions[progression].stages
    updates = [
        StageUpdate(
            stage_id=stage.id,
            open_ended=form.get(f"infinite__{stage.id}") == "on",
            target_minutes=_parse_minutes(form.get(f"minutes__{stage.id}")),
        )
        for stage in stages
    ]

    try:
        config.progressions[progression] = apply_stage_updates(
            config.progressions[progression], updates
        )
    except (StageEditNotAllowed, ValidationError) as error:
        context = _dashboard_context(request, progression, config, history)
        context["save_error"] = str(error)
        return templates.TemplateResponse(
            request,
            "_stage_editor.html",
            context,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    backup_config(config_path)
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="python"), sort_keys=False), encoding="utf-8"
    )

    context = _dashboard_context(request, progression, config, history)
    context["saved"] = True
    return templates.TemplateResponse(request, "_stage_editor.html", context)


def _parse_minutes(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@router.post(
    "/api/generate/{progression}", response_class=HTMLResponse, dependencies=[Depends(require_auth)]
)
def generate(
    request: Request,
    progression: str,
    config: Config = Depends(get_config),
    client: SpotifyClient = Depends(get_spotify_client),
    history: PlayHistory = Depends(get_history),
) -> HTMLResponse:
    if progression not in config.progressions:
        raise HTTPException(status_code=404, detail=f'unknown progression "{progression}"')

    progression_label = _progression_label(progression)
    try:
        results = rebuild_progression(progression, config, client, history)
    except (requests.RequestException, RuntimeError) as error:
        # Spotify/auth/network failure: report it and leave the saved config untouched —
        # generation never writes to config, so there's nothing to roll back.
        return templates.TemplateResponse(
            request,
            "_generate_result.html",
            {"error_message": f"Generate failed for {progression_label}: {error}"},
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    stage_colors = stage_colors_for([stage.id for stage in config.progressions[progression].stages])
    return templates.TemplateResponse(
        request,
        "_generate_result.html",
        {
            "results": results,
            "stage_colors": stage_colors,
            "heading": f"Generated {progression_label}",
            "last_generated": history.last_generated_at(progression),
        },
    )
