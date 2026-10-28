from __future__ import annotations

import os

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .errors import AuthConfigurationRequired, RadixError

bearer = HTTPBearer(auto_error=False)


def require_local_workflow_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """Allow anonymous access to stateless workflow endpoints only in explicit local mode."""
    local_mode = (
        os.getenv("RADIX_ENV", "production").casefold() == "development"
        and os.getenv("RADIX_JD_AUTH_MODE", "supabase").casefold() == "local"
    )
    if local_mode:
        return {"id": "local-development"}
    return require_supabase_user(credentials)


def require_supabase_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise RadixError(401, "AUTHENTICATION_REQUIRED", "A Supabase access token is required.")

    settings = get_settings()
    if not settings.auth_configured:
        raise AuthConfigurationRequired()

    try:
        response = httpx.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key or "",
                "Authorization": f"Bearer {credentials.credentials}",
            },
            timeout=5.0,
        )
    except httpx.RequestError:
        raise RadixError(
            503,
            "AUTH_PROVIDER_UNAVAILABLE",
            "Supabase Auth could not be reached to validate the session.",
        ) from None

    if response.status_code in (401, 403):
        raise RadixError(401, "INVALID_ACCESS_TOKEN", "The Supabase access token is invalid or expired.")
    if response.status_code != 200:
        raise RadixError(503, "AUTH_PROVIDER_UNAVAILABLE", "Supabase Auth could not validate the session.")

    try:
        user = response.json()
    except ValueError:
        raise RadixError(503, "AUTH_PROVIDER_UNAVAILABLE", "Supabase Auth returned an invalid response.") from None
    if not isinstance(user, dict) or not isinstance(user.get("id"), str):
        raise RadixError(401, "INVALID_ACCESS_TOKEN", "The Supabase access token is invalid or expired.")
    return {"id": user["id"]}
