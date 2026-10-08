import secrets
import logging

from google.auth.exceptions import GoogleAuthError
from fastapi import Request
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from pydantic import TypeAdapter
from postgrest.exceptions import APIError
from requests.exceptions import RequestException
from supabase import Client

from app.api.v1.auth.helper import create_tokens, set_token_cookies
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
	create_flow,
)
from app.api.v1.google_auth.types import GoogleIdentity
from app.api.v1.google_auth.calendar_helper import set_google_access_cookie
from app.config import settings
from app.models.google_refresh_token import GoogleRefreshTokenRecord
from app.models.user import UserRecord

logger = logging.getLogger(__name__)


def _get_user_id(supabase: Client, email: str) -> str:
	result = (
		supabase.table("users")
		.select("id,email")
		.ilike(
			"email",
			email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"),
		)
		.limit(2)
		.execute()
	)
	users = TypeAdapter(list[UserRecord]).validate_python(result.data)
	matches = [user for user in users if user.email.casefold() == email.casefold()]
	if len(matches) == 1:
		return matches[0].id
	if len(matches) > 1:
		raise GoogleIdentityException(
			"More than one application user matches this Google email address."
		)

	try:
		result = (
			supabase.table("users")
			.insert(
				{
					"email": email,
					"name": email.partition("@")[0],
				}
			)
			.execute()
		)
	except APIError as error:
		if error.code != "23505":
			raise
		return _get_user_id(supabase, email)
	users = TypeAdapter(list[UserRecord]).validate_python(result.data)
	if len(users) != 1:
		raise GoogleIdentityException("Could not create the application user.")
	return users[0].id


def _is_allowed_email(email: str) -> bool:
	local_part, separator, domain = email.rpartition("@")
	return bool(
		separator
		and local_part
		and domain.casefold() in {"student.pradita.ac.id", "pradita.ac.id"}
	)


def _needs_onboarding(supabase: Client, user_id: str) -> bool:
	result = (
		supabase.table("users")
		.select("nim,major")
		.eq("id", user_id)
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
	redirect.delete_cookie(
		key=OAUTH_STATE_COOKIE,
		httponly=True,
		secure=settings.COOKIE_SECURE,
		samesite="lax",
		path=OAUTH_STATE_COOKIE_PATH,
	)
	return redirect


def _get_refresh_token(supabase: Client, user_id: str, credentials: Credentials) -> str:
	if credentials.refresh_token:
		return encrypt_refresh_token(credentials.refresh_token)
	result = (
		supabase.table("google_refresh_tokens")
		.select("refresh_token,is_valid")
		.eq("id", user_id)
		.limit(1)
		.execute()
	)
	rows = TypeAdapter(list[GoogleRefreshTokenRecord]).validate_python(result.data)
	if not rows or not rows[0].is_valid:
		raise GoogleRefreshConsentException()
	return rows[0].refresh_token


def complete_google_oauth(
	request: Request,
	supabase: Client,
	oauth_state: str | None,
) -> RedirectResponse:
	query_state = request.query_params.get("state")
	if not oauth_state or not query_state or not secrets.compare_digest(
		oauth_state, query_state
	):
		raise GoogleOAuthStateException()
	if request.query_params.get("error"):
		return _failure_redirect("google_access_denied")

	code = request.query_params.get("code")
	if not code:
		raise GoogleOAuthRequestException("Google did not return an authorization code.")
	flow = create_flow(oauth_state)
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
	except GoogleAuthError as error:
		raise GoogleCredentialException(
			"Google identity verification is temporarily unavailable."
		) from error
	except ValueError as error:
		raise GoogleIdentityException("Google returned an invalid identity token.") from error
	if not identity.email or not identity.email_verified:
		return _failure_redirect("verified_email_required")
	email = str(identity.email).strip().casefold()
	if not _is_allowed_email(email):
		return _failure_redirect("university_email_required")
	if not credentials.token:
		raise GoogleCredentialException("Google did not return an access token.")

	user_id = _get_user_id(supabase, email)
	try:
		encrypted_refresh_token = _get_refresh_token(
			supabase,
			user_id,
			credentials,
		)
	except GoogleRefreshConsentException:
		return _failure_redirect("calendar_consent_required")
	supabase.table("google_refresh_tokens").upsert(
		{
			"id": user_id,
			"refresh_token": encrypted_refresh_token,
			"is_valid": True,
		},
		on_conflict="id",
	).execute()

	app_access_token, app_refresh_token = create_tokens(user_email=email)
	destination = "/onboarding" if _needs_onboarding(supabase, user_id) else "/booking-form"
	redirect = RedirectResponse(
		f"{settings.FRONTEND_URL.rstrip('/')}{destination}",
		status_code=303,
	)
	set_token_cookies(redirect, app_access_token, app_refresh_token)
	set_google_access_cookie(redirect, credentials.token, credentials.expiry)
	redirect.delete_cookie(
		key=OAUTH_STATE_COOKIE,
		httponly=True,
		secure=settings.COOKIE_SECURE,
		samesite="lax",
		path=OAUTH_STATE_COOKIE_PATH,
	)
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
