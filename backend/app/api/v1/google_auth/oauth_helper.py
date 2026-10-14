import logging
import secrets

from fastapi import Request
from fastapi.responses import RedirectResponse
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from postgrest.exceptions import APIError
from pydantic import TypeAdapter
from requests.exceptions import RequestException
from supabase import Client
from supabase_auth.errors import AuthError

from app.api.v1.auth.helper import set_token_cookies
from app.api.v1.google_auth.calendar_helper import set_google_access_cookie
from app.api.v1.google_auth.exceptions import (
	GoogleCredentialException,
	GoogleIdentityException,
	GoogleOAuthRequestException,
	GoogleOAuthStateException,
	GoogleRefreshConsentException,
)
from app.api.v1.google_auth.helper import encrypt_refresh_token
from app.api.v1.google_auth.oauth_flow import (
	OAUTH_STATE_COOKIE,
	OAUTH_STATE_COOKIE_PATH,
	OAUTH_VERIFIER_COOKIE,
	create_flow,
	clear_oauth_cookies
)

from app.api.v1.google_auth.types import GoogleIdentity
from app.config import settings
from app.database import create_supabase_client
from app.models.google_refresh_token import GoogleRefreshTokenRecord

logger = logging.getLogger(__name__)
TOKEN_RECORDS = TypeAdapter(list[GoogleRefreshTokenRecord])


def _is_allowed_email(email: str) -> bool:
	local_part, separator, domain = email.rpartition("@")
	return bool(
		separator
		and local_part
		and domain.casefold() in {"student.pradita.ac.id", "pradita.ac.id"}
	)


def _needs_onboarding(supabase: Client, profile_id: str) -> bool:
	result = (
		supabase.table("users")
		.select("nim,major")
		.eq("id", profile_id)
		.limit(1)
		.execute()
	)
	if not result.data or not isinstance(result.data[0], dict):
		raise GoogleIdentityException("Could not load the application user profile.")
	return result.data[0].get("nim") is None or result.data[0].get("major") is None


def _failure_redirect(error_code: str) -> RedirectResponse:
	redirect = RedirectResponse(
		f"{settings.FRONTEND_URL.rstrip('/')}?auth_error={error_code}",
		status_code=303,
	)
	clear_oauth_cookies(redirect)
	return redirect


def _backend_rpc_secret() -> str:
	if not settings.SUPABASE_BACKEND_RPC_SECRET:
		raise GoogleCredentialException(
			"Backend Supabase RPC authorization is not configured."
		)
	return settings.SUPABASE_BACKEND_RPC_SECRET


def _get_refresh_token(
	supabase: Client,
	profile_id: str,
	credentials: Credentials,
) -> str:
	if credentials.refresh_token:
		return encrypt_refresh_token(credentials.refresh_token)
	result = supabase.rpc(
		"get_google_refresh_token",
		{
			"requested_profile_id": profile_id,
			"backend_secret": _backend_rpc_secret(),
		},
	).execute()
	rows = TOKEN_RECORDS.validate_python(result.data)
	if not rows or not rows[0].is_valid:
		raise GoogleRefreshConsentException()
	return rows[0].refresh_token


def complete_google_oauth(
	state:str | None,
	code:str | None,
	error: str | None,
	supabase: Client,
	oauth_state: str | None,
	oauth_verifier:str | None
) -> RedirectResponse:
	if not oauth_state or not state or not secrets.compare_digest(oauth_state, state):
		raise GoogleOAuthStateException()
	if error:
		return _failure_redirect("google_access_denied")

	if not code:
		raise GoogleOAuthRequestException("Google did not return an authorization code.")
	if not oauth_verifier:
		raise GoogleOAuthStateException()
	flow = create_flow(oauth_state, code_verifier=oauth_verifier)
	try:
		flow.fetch_token(code=code)
	except (OAuth2Error, RequestException):
		logger.warning("Google OAuth token exchange failed.", exc_info=True)
		return _failure_redirect("google_exchange_failed")
	credentials = flow.credentials
	if not isinstance(credentials, Credentials) or not credentials.id_token:
		raise GoogleCredentialException("Google did not provide valid credentials.")
	try:
		identity = GoogleIdentity.model_validate(
			id_token.verify_oauth2_token(
				credentials.id_token,
				GoogleAuthRequest(),
				settings.GOOGLE_CLIENT_ID,
			)
		)
	except GoogleAuthError as e:
		raise GoogleCredentialException(
			"Google identity verification is temporarily unavailable."
		) from e
	except ValueError as e:
		raise GoogleIdentityException("Google returned an invalid identity token.") from e
	if not identity.sub or not identity.email or not identity.email_verified:
		return _failure_redirect("verified_email_required")
	email = identity.email.strip().casefold()
	if not _is_allowed_email(email):
		return _failure_redirect("university_email_required")
	if not credentials.token:
		raise GoogleCredentialException("Google did not return an access token.")

	try:
		auth_response = supabase.auth.sign_in_with_id_token(
			{"provider": "google", "token": credentials.id_token}
		)
	except AuthError as e:
		logger.exception(
			"Supabase Auth failed during Google ID-token sign-in."
		)
		raise GoogleCredentialException("Supabase Auth could not establish a session.") from e

	if auth_response.session is None or auth_response.user is None:
		raise GoogleCredentialException("Supabase Auth did not return a valid session.")
	auth_user = auth_response.user
	if (
		not auth_user.email
		or auth_user.email.casefold() != email
		or auth_user.email_confirmed_at is None
	):
		raise GoogleIdentityException(
			"Supabase Auth identity did not match the verified Google account."
		)

	session = auth_response.session
	user_supabase = create_supabase_client(session.access_token)
	try:
		profile_result = user_supabase.rpc(
			"get_or_create_current_profile",
			{"profile_name": identity.name or email.partition("@")[0]},
		).execute()
	except APIError as e:
		if e.code == "P0001":
			return _failure_redirect("account_link_required")
		raise
	profile_id = profile_result.data
	if not isinstance(profile_id, str) or not profile_id:
		raise GoogleIdentityException("Could not load the application user profile.")

	try:
		encrypted_refresh_token = _get_refresh_token(
			user_supabase,
			profile_id,
			credentials,
		)
	except GoogleRefreshConsentException:
		return _failure_redirect("calendar_consent_required")
	user_supabase.rpc(
		"store_google_refresh_token",
		{"token_value": encrypted_refresh_token},
	).execute()

	destination = (
		"/onboarding"
		if _needs_onboarding(user_supabase, profile_id)
		else "/booking-form"
	)
	redirect = RedirectResponse(
		f"{settings.FRONTEND_URL.rstrip('/')}{destination}",
		status_code=303,
	)
	set_token_cookies(
		redirect,
		session.access_token,
		session.refresh_token,
		session.expires_in,
	)
	set_google_access_cookie(redirect, credentials.token, credentials.expiry)
	clear_oauth_cookies(redirect)
	redirect.set_cookie(
		key="csrf_token",
		value=secrets.token_urlsafe(32),
		max_age=30 * 24 * 60 * 60,
		httponly=False,
		secure=settings.COOKIE_SECURE,
		samesite=settings.COOKIE_SAMESITE,
		path="/",
	)
	return redirect
