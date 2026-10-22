from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.config import settings
from app.google_api.exceptions import (
	GoogleConfigurationException,
	GoogleCredentialException,
	GoogleIdentityException,
)
from app.google_api.types import GoogleIdentity

SCOPES = [
	"openid",
	"https://www.googleapis.com/auth/userinfo.email",
	"https://www.googleapis.com/auth/userinfo.profile",
	"https://www.googleapis.com/auth/calendar.events",
]


def create_flow(state: str | None = None, code_verifier: str | None = None) -> Flow:
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
		code_verifier=code_verifier,
	)


def verify_google_identity(raw_id_token: str) -> GoogleIdentity:
	"""Check the id token's signature and audience with Google and return who it names."""
	try:
		return GoogleIdentity.model_validate(
			id_token.verify_oauth2_token(
				raw_id_token,
				GoogleAuthRequest(),
				settings.GOOGLE_CLIENT_ID,
				clock_skew_in_seconds=10,
			)
		)
	except GoogleAuthError as e:
		raise GoogleCredentialException(
			"Google identity verification is temporarily unavailable."
		) from e
	except ValueError as e:
		raise GoogleIdentityException("Google returned an invalid identity token.") from e
