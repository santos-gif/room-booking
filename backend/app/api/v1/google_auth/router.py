import logging

from fastapi import APIRouter, Cookie, Query
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.api.v1.google_auth.callback import complete_google_oauth, failure_redirect
from app.api.v1.google_auth.login import create_google_login_response
from app.cookies import OAUTH_STATE_COOKIE, OAUTH_VERIFIER_COOKIE
from app.database import PublicSupabaseClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/google-auth")


@router.get("/login", response_class=RedirectResponse, response_model=None)
async def login() -> RedirectResponse:
	# Also a browser navigation: a misconfigured Google client must not show raw JSON to the student.
	try:
		return create_google_login_response()
	except Exception:
		logger.exception("Could not start Google sign-in.")
		return failure_redirect("server_unavailable")


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
	except Exception:
		logger.exception("Google sign-in callback failed.")
		return failure_redirect("google_exchange_failed")

