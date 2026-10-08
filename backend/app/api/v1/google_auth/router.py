from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.google_auth.calendar_helper import (
	GOOGLE_ACCESS_COOKIE,
	GOOGLE_ACCESS_EXPIRY_COOKIE,
	get_calendar_events,
)
from app.api.v1.google_auth.oauth_flow import create_google_login_response
from app.api.v1.google_auth.oauth_flow import OAUTH_STATE_COOKIE
from app.api.v1.google_auth.oauth_helper import complete_google_oauth
from app.api.v1.google_auth.types import GoogleCalendarEvent
from app.database import SupabaseClient

router = APIRouter(prefix="/google-auth")


@router.get("/login", response_class=RedirectResponse, response_model=None)
async def login() -> RedirectResponse:
	return create_google_login_response()


@router.get("/oauth2callback", response_class=RedirectResponse, response_model=None)
async def oauth2callback(
	request: Request,
	supabase: SupabaseClient,
	oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
) -> RedirectResponse:
	return await run_in_threadpool(
		complete_google_oauth, request, supabase, oauth_state
	)


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
