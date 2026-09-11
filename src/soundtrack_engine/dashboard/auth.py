"""Single-password auth for the dashboard: no user accounts, no OAuth — just a
shared password (bcrypt-hashed, stored in the environment) and a signed, timed
session cookie. This is a personal, single-user control panel exposed to the
internet (via a tunnel), not a multi-tenant app — this is deliberately the
simplest thing that still keeps a bare password off the wire after login and
keeps a stolen cookie from working forever.
"""

from __future__ import annotations

import os

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_COOKIE_NAME = "dashboard_session"
_SESSION_SALT = "soundtrack-engine-dashboard-session"
_SESSION_VALUE = "authenticated"


class AuthNotConfiguredError(RuntimeError):
    """Raised when DASHBOARD_PASSWORD_HASH / DASHBOARD_SECRET_KEY aren't set."""


def _password_hash() -> str:
    value = os.environ.get("DASHBOARD_PASSWORD_HASH")
    if not value:
        raise AuthNotConfiguredError(
            "DASHBOARD_PASSWORD_HASH must be set (run "
            "`soundtrack-engine hash-password` to generate one)."
        )
    return value


def _secret_key() -> str:
    value = os.environ.get("DASHBOARD_SECRET_KEY")
    if not value:
        raise AuthNotConfiguredError("DASHBOARD_SECRET_KEY must be set (any long random string).")
    return value


def session_max_age_seconds() -> int:
    days = int(os.environ.get("DASHBOARD_SESSION_DAYS", "30"))
    return days * 24 * 60 * 60


def cookie_is_secure() -> bool:
    """Whether the session cookie should be marked Secure (HTTPS-only). Defaults to
    true — behind Cloudflare Tunnel the browser only ever sees HTTPS even though the
    tunnel's local hop to this process is plain HTTP. Set
    DASHBOARD_COOKIE_SECURE=false only for local development over plain http.
    """
    return os.environ.get("DASHBOARD_COOKIE_SECURE", "true").lower() != "false"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt=_SESSION_SALT)


def hash_password(plain_password: str) -> str:
    """Hash a password for storing in DASHBOARD_PASSWORD_HASH."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str) -> bool:
    """Check a submitted password against DASHBOARD_PASSWORD_HASH."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), _password_hash().encode("ascii"))


def create_session_token() -> str:
    """Produce a signed, timestamped token to set as the session cookie's value."""
    return _serializer().dumps(_SESSION_VALUE)


def session_token_is_valid(token: str | None) -> bool:
    """Check a session cookie's value: correctly signed and not past
    DASHBOARD_SESSION_DAYS old.
    """
    if not token:
        return False
    try:
        value = _serializer().loads(token, max_age=session_max_age_seconds())
    except (BadSignature, SignatureExpired):
        return False
    return value == _SESSION_VALUE
