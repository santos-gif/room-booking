import secrets

from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from app.api.v1.google_auth.exceptions import GoogleConfigurationException
from app.config import settings

SCOPES = [
	"openid",
	"email",
	"profile",
	"https://www.googleapis.com/auth/calendar.events",
]
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/api/v1/google-auth"


def create_flow(state: str | None = None) -> Flow:
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
	)


def create_google_login_response() -> RedirectResponse:
	state = secrets.token_urlsafe(32)
	flow = create_flow(state)
	authorization_url, _ = flow.authorization_url(
		access_type="offline",
		prompt="select_account consent",
		include_granted_scopes="true",
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
	return response
