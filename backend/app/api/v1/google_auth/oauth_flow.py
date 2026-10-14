import secrets
from typing import Optional

from fastapi import Response
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from app.api.v1.google_auth.exceptions import GoogleConfigurationException
from app.config import settings

SCOPES = [
	"openid",
	"https://www.googleapis.com/auth/userinfo.email",
	"https://www.googleapis.com/auth/userinfo.profile",
	"https://www.googleapis.com/auth/calendar.events",
	"https://www.googleapis.com/auth/calendar.events",
]
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/api/v1/google-auth"
OAUTH_VERIFIER_COOKIE = "google_oauth_verifier"

def create_flow(state: Optional[str] = None, code_verifier:Optional[str] = None) -> Flow:
	if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
		raise GoogleConfigurationException(
			"GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured."
		)
	client_config = {
		"web": {
			"client_id": settings.GOOGLE_CLIENT_ID,
			"client_secret": settings.GOOGLE_CLIENT_SECRET,
			"auth_uri": "https://accounts.google.com/o/oauth2/auth",
			"token_uri": "https://oauth2.googleapis.com/token",
			"redirect_uris": [settings.GOOGLE_REDIRECT_URI],
		}
	}
	return Flow.from_client_config(
		client_config,
		scopes=SCOPES,
		redirect_uri=settings.GOOGLE_REDIRECT_URI,
		state=state,
		code_verifier=code_verifier
	)


def create_google_login_response() -> RedirectResponse:
	code_verifier = secrets.token_urlsafe(64)

	state = secrets.token_urlsafe(32)
	flow = create_flow(state, code_verifier)
	authorization_url, _ = flow.authorization_url(
		access_type="offline",
		prompt="select_account consent",
		include_granted_scopes="true",
		code_challenge_method="S256"
	)
	response = RedirectResponse(authorization_url, status_code=302)
	response.set_cookie(
		key=OAUTH_STATE_COOKIE,
		value=state,
		max_age=600,
		httponly=True,
		secure=settings.COOKIE_SECURE,
		samesite="lax",
		path=OAUTH_STATE_COOKIE_PATH,
	)
	response.set_cookie(
		key=OAUTH_VERIFIER_COOKIE,
		value=code_verifier,
		max_age=600,
		httponly=True,
		secure=settings.COOKIE_SECURE,
		samesite="lax",
		path=OAUTH_STATE_COOKIE_PATH,
	)
	return response
def clear_oauth_cookies(response: RedirectResponse) -> None:
	for cookie_name in (OAUTH_STATE_COOKIE, OAUTH_VERIFIER_COOKIE):
		response.delete_cookie(
			key=cookie_name,
			httponly=True,
			secure=settings.COOKIE_SECURE,
			samesite="lax",
			path=OAUTH_STATE_COOKIE_PATH,
		)
