import logging

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.google_auth.callback import _failure_redirect, complete_google_oauth
from app.api.v1.google_auth.login import create_google_login_response
from app.cookies import (
	GOOGLE_ACCESS_COOKIE,
	GOOGLE_ACCESS_EXPIRY_COOKIE,
	OAUTH_STATE_COOKIE,
	OAUTH_VERIFIER_COOKIE,
)
from app.database import PublicSupabaseClient, SupabaseClient
from app.google_api.calendar_api import get_calendar_events
from app.google_api.exceptions import GoogleRefreshConsentException
from app.google_api.types import GoogleCalendarEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/google-auth")


@router.get("/login", response_class=RedirectResponse, response_model=None)
async def login() -> RedirectResponse:
	# Also a browser navigation: a misconfigured Google client must not show raw JSON to the student.
	try:
		return create_google_login_response()
	except Exception:
		logger.exception("Could not start Google sign-in.")
		return _failure_redirect("server_unavailable")


@router.get("/oauth2callback", response_class=RedirectResponse, response_model=None)
async def oauth2callback(
	supabase: PublicSupabaseClient,
	state: str | None = Query(None),
	code: str | None = Query(None),
	error:str | None = Query(None),
	oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
	oauth_verifier: str | None = Cookie(default=None, alias=OAUTH_VERIFIER_COOKIE)
) -> RedirectResponse:
	# A browser navigation cannot show JSON, so every failure becomes a login-page redirect.
	try:
		return await run_in_threadpool(
			complete_google_oauth,
			state=state,
			code=code,
			error=error,
			supabase=supabase,
			oauth_state=oauth_state,
			oauth_verifier=oauth_verifier
		)
	except GoogleRefreshConsentException:
		logger.warning("Google did not grant offline Calendar access.")
		return _failure_redirect("calendar_consent_required")
	except Exception:
		logger.exception("Google sign-in callback failed.")
		return _failure_redirect("google_exchange_failed")


@router.get("/events", response_model=list[GoogleCalendarEvent])
async def calendar_events(
	response: Response,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
	google_access_token: str | None = Cookie(default=None, alias=GOOGLE_ACCESS_COOKIE),
	google_access_token_expires_at: int | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_EXPIRY_COOKIE,
	),
) -> list[GoogleCalendarEvent]:
	return await run_in_threadpool(
		get_calendar_events,
		supabase,
		current_user.id,
		google_access_token,
		google_access_token_expires_at,
		response,
	)
