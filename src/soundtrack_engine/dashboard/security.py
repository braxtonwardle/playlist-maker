"""FastAPI-specific glue around auth.py: the dependency every dashboard route (other
than /login) requires, plus the exception handler that turns a failed check into the
right kind of redirect — a normal 303 for a full page load, an `HX-Redirect` header
for an HTMX request (a plain 401 would otherwise render as an error swapped into the
page instead of sending the browser to the login screen).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from soundtrack_engine.dashboard import auth

LOGIN_PATH = "/login"


class NotAuthenticated(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def require_auth(request: Request) -> None:
    token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    if not auth.session_token_is_valid(token):
        raise NotAuthenticated()


def register_auth_redirect(app: FastAPI) -> None:
    @app.exception_handler(NotAuthenticated)
    async def _redirect_to_login(request: Request, exc: NotAuthenticated):
        if request.headers.get("HX-Request") == "true":
            from fastapi import Response

            response = Response(status_code=status.HTTP_200_OK)
            response.headers["HX-Redirect"] = LOGIN_PATH
            return response
        return RedirectResponse(LOGIN_PATH, status_code=status.HTTP_303_SEE_OTHER)
