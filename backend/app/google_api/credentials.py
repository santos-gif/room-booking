from datetime import datetime, timezone

from fastapi import Response
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from supabase import Client

from app.config import settings
from app.cookies import set_google_access_cookie
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
	GoogleUnavailableException,
)
from app.google_api.oauth import SCOPES
from app.google_api.token_crypto import decrypt_refresh_token
from app.queries.google_tokens import invalidate_refresh_token, load_refresh_token

REFRESH_TIMEOUT_SEC = 4
REFRESH_ATTEMPTS = 2


class _TimedRequest(GoogleAuthRequest):
	"""google-auth waits 120 s by default; a hung Google call must not hold a booking that long."""

	def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
		kwargs.setdefault("timeout", REFRESH_TIMEOUT_SEC)
		return super().__call__(*args, **kwargs)


def _refresh(supabase: Client, user_id: str, credentials: Credentials) -> None:
	"""Only Google's `invalid_grant` verdict kills the stored token; a timeout or 5xx is retried, then reported."""
	last_error: Exception | None = None
	for _ in range(REFRESH_ATTEMPTS):
		try:
			credentials.refresh(_TimedRequest())
			return
		except RefreshError as error:
			if "invalid_grant" in str(error):
				invalidate_refresh_token(supabase, user_id)
				raise GoogleAuthorizationException(
					"Google authorization expired or was revoked. Connect Google Calendar again."
				) from error
			last_error = error
		except TransportError as error:
			last_error = error
	raise GoogleUnavailableException() from last_error


# Known leftover: it still takes `response` and sets the refreshed-token cookie, an accepted
# exception to "google_api builds no HTTP responses".
def calendar_credentials(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> Credentials:
	refresh_token = load_refresh_token(
		supabase, user_id, settings.SUPABASE_BACKEND_RPC_SECRET
	)
	if refresh_token is None:
		raise GoogleRefreshTokenException(
			"No valid Google Calendar connection is available for this user."
		)
	expiry = (
		datetime.fromtimestamp(expires_at, timezone.utc).replace(tzinfo=None)
		if expires_at is not None
		else None
	)
	credentials = Credentials(
		token=access_token,
		refresh_token=decrypt_refresh_token(refresh_token),
		token_uri="https://oauth2.googleapis.com/token",
		client_id=settings.GOOGLE_CLIENT_ID,
		client_secret=settings.GOOGLE_CLIENT_SECRET,
		scopes=SCOPES,
		expiry=expiry,
	)
	if not credentials.token or credentials.expired:
		_refresh(supabase, user_id, credentials)
		if not credentials.token:
			raise GoogleCredentialException("Google did not return an access token.")
		set_google_access_cookie(response, credentials.token, credentials.expiry)
	return credentials
