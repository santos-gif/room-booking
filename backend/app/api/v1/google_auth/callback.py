"""Finishing a Google sign-in: the code becomes a Google identity, a Supabase session and a profile."""
import logging
import secrets

from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from requests.exceptions import RequestException
from supabase import Client
from supabase_auth.types import Session

from app.api.v1.google_auth.callback_identity import SignInRefused, verified_university_email
from app.api.v1.google_auth.callback_profile import profile_id_for, save_refresh_token, supabase_session
from app.config import settings
from app.cookies import (
	clear_oauth_cookies,
	set_csrf_cookie,
	set_google_access_cookie,
	set_token_cookies,
)
from app.database import create_supabase_client
from app.google_api.exceptions import (
	GoogleCredentialException,
	GoogleIdentityException,
	GoogleOAuthRequestException,
	GoogleOAuthStateException,
)
from app.google_api.oauth import create_flow, verify_google_identity

logger = logging.getLogger(__name__)


def complete_google_oauth(
	state: str | None,
	code: str | None,
	error: str | None,
	supabase: Client | None,
	oauth_state: str | None,
	oauth_verifier: str | None,
) -> RedirectResponse:
	"""Every refusal ends as a redirect to the login page with a fixed error code, never a message."""
	try:
		return _sign_in(state, code, error, supabase, oauth_state, oauth_verifier)
	except SignInRefused as refused:
		return failure_redirect(refused.code)


def _sign_in(
	state: str | None,
	code: str | None,
	error: str | None,
	supabase: Client | None,
	oauth_state: str | None,
	oauth_verifier: str | None,
) -> RedirectResponse:
	if not supabase:
		raise GoogleCredentialException("Supabase client is required.")
	credentials = _exchange_code(state, code, error, oauth_state, oauth_verifier)
	identity = verify_google_identity(str(credentials.id_token))
	email = verified_university_email(identity)
	if not credentials.token:
		raise GoogleCredentialException("Google did not return an access token.")
	session = supabase_session(supabase, str(credentials.id_token), email)
	user_supabase = create_supabase_client(session.access_token)
	profile_id = profile_id_for(user_supabase, identity.name, email)
	save_refresh_token(user_supabase, profile_id, credentials)
	return _success_redirect(user_supabase, profile_id, session, credentials)


def _exchange_code(
	state: str | None,
	code: str | None,
	error: str | None,
	oauth_state: str | None,
	oauth_verifier: str | None,
) -> Credentials:
	"""Checks the request really answers our login redirect, then trades the code for tokens."""
	if not oauth_state or not state or not secrets.compare_digest(oauth_state, state):
		raise GoogleOAuthStateException()
	if error:
		raise SignInRefused("google_access_denied")
	if not code or not isinstance(code, str):
		raise GoogleOAuthRequestException("Google did not return an authorization code.")
	if not oauth_verifier:
		raise GoogleOAuthStateException()
	flow = create_flow(oauth_state, code_verifier=oauth_verifier)
	try:
		flow.fetch_token(code=code)
	except Warning as warning:
		# oauthlib raises Warning("Scope has changed") when the user unticks the Calendar scope.
		logger.warning("Google returned fewer scopes than requested.", exc_info=True)
		raise SignInRefused("calendar_consent_required") from warning
	except (OAuth2Error, RequestException) as failure:
		logger.warning("Google OAuth token exchange failed.", exc_info=True)
		raise SignInRefused("google_exchange_failed") from failure
	credentials = flow.credentials
	if not isinstance(credentials, Credentials) or not credentials.id_token:
		raise GoogleCredentialException("Google did not provide valid credentials.")
	return credentials


def _success_redirect(
	user_supabase: Client, profile_id: str, session: Session, credentials: Credentials
) -> RedirectResponse:
	"""Signed in: new students go to onboarding, everyone else to My bookings, with the session cookies set."""
	result = user_supabase.table("users").select("nim,major").eq("id", profile_id).limit(1).execute()
	if not result.data or not isinstance(result.data[0], dict):
		raise GoogleIdentityException("Could not load the application user profile.")
	profile = result.data[0]
	new_student = profile.get("nim") is None or profile.get("major") is None
	destination = "/onboarding" if new_student else "/my-bookings"
	redirect = RedirectResponse(f"{settings.FRONTEND_URL.rstrip('/')}{destination}", status_code=303)
	set_token_cookies(redirect, session.access_token, session.refresh_token, session.expires_in)
	set_google_access_cookie(redirect, credentials.token, credentials.expiry)
	clear_oauth_cookies(redirect)
	set_csrf_cookie(redirect)
	return redirect


def failure_redirect(error_code: str) -> RedirectResponse:
	"""Back to the login page. Only a fixed code travels in the URL; the page maps it to a message."""
	redirect = RedirectResponse(f"{settings.FRONTEND_URL.rstrip('/')}?auth_error={error_code}", status_code=303)
	clear_oauth_cookies(redirect)
	return redirect
