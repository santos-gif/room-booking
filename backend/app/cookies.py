"""Every cookie name the backend uses, and the helpers that set or clear them."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
GOOGLE_ACCESS_COOKIE = "google_access_token"
GOOGLE_ACCESS_EXPIRY_COOKIE = "google_access_token_expires_at"
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_VERIFIER_COOKIE = "google_oauth_verifier"
# The two OAuth cookies are only sent back to the Google routes.
OAUTH_COOKIE_PATH = "/api/v1/google-auth"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _session_cookie_options() -> dict[str, Any]:
	return {
		"httponly": True,
		"secure": settings.COOKIE_SECURE,
		"samesite": settings.COOKIE_SAMESITE,
		"path": "/",
	}


def set_token_cookies(
	response: Response,
	access_token: str,
	refresh_token: str,
	access_max_age: int = 3600,
) -> None:
	response.set_cookie(
		key=ACCESS_COOKIE,
		value=access_token,
		max_age=max(0, access_max_age),
		**_session_cookie_options(),
	)
	response.set_cookie(
		key=REFRESH_COOKIE,
		value=refresh_token,
		max_age=REFRESH_COOKIE_MAX_AGE,
		**_session_cookie_options(),
	)


def set_google_access_cookie(
	response: Response,
	access_token: str,
	expires_at: datetime | None,
) -> None:
	now = datetime.now(timezone.utc)
	if expires_at is None:
		expires_at = now + timedelta(hours=1)
	elif expires_at.tzinfo is None:
		expires_at = expires_at.replace(tzinfo=timezone.utc)
	else:
		expires_at = expires_at.astimezone(timezone.utc)
	max_age = max(0, int((expires_at - now).total_seconds()))
	cookie_options = {**_session_cookie_options(), "max_age": max_age}
	response.set_cookie(key=GOOGLE_ACCESS_COOKIE, value=access_token, **cookie_options)
	response.set_cookie(
		key=GOOGLE_ACCESS_EXPIRY_COOKIE,
		value=str(int(expires_at.timestamp())),
		**cookie_options,
	)


def set_csrf_cookie(response: Response) -> None:
	# Not httponly: the frontend must read it and echo it back in a header.
	response.set_cookie(
		key=CSRF_COOKIE,
		value=secrets.token_urlsafe(32),
		max_age=30 * 24 * 60 * 60,
		httponly=False,
		secure=settings.COOKIE_SECURE,
		samesite=settings.COOKIE_SAMESITE,
		path="/",
	)


def clear_auth_cookies(response: Response) -> None:
	for name in (ACCESS_COOKIE, REFRESH_COOKIE, GOOGLE_ACCESS_COOKIE, GOOGLE_ACCESS_EXPIRY_COOKIE):
		response.delete_cookie(key=name, **_session_cookie_options())
	response.delete_cookie(
		key=CSRF_COOKIE,
		httponly=False,
		secure=settings.COOKIE_SECURE,
		samesite=settings.COOKIE_SAMESITE,
		path="/",
	)


def set_oauth_cookies(response: Response, state: str, code_verifier: str) -> None:
	for name, value in ((OAUTH_STATE_COOKIE, state), (OAUTH_VERIFIER_COOKIE, code_verifier)):
		response.set_cookie(
			key=name,
			value=value,
			max_age=600,
			httponly=True,
			secure=settings.COOKIE_SECURE,
			samesite="lax",
			path=OAUTH_COOKIE_PATH,
		)


def clear_oauth_cookies(response: Response) -> None:
	for name in (OAUTH_STATE_COOKIE, OAUTH_VERIFIER_COOKIE):
		response.delete_cookie(
			key=name,
			httponly=True,
			secure=settings.COOKIE_SECURE,
			samesite="lax",
			path=OAUTH_COOKIE_PATH,
		)
