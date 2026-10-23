"""After Google says who the student is: their Supabase session, their profile, their Calendar token."""
import logging

from google.oauth2.credentials import Credentials
from postgrest.exceptions import APIError
from supabase import Client
from supabase_auth.errors import AuthError
from supabase_auth.types import Session

from app.api.v1.google_auth.callback_identity import SignInRefused
from app.config import settings
from app.google_api.exceptions import (
	GoogleCredentialException,
	GoogleIdentityException,
	GoogleRefreshConsentException,
)
from app.google_api.token_crypto import encrypt_refresh_token
from app.queries.google_tokens import load_refresh_token, store_refresh_token

logger = logging.getLogger(__name__)


def supabase_session(supabase: Client, id_token: str, email: str) -> Session:
	"""Signs the verified Google identity in to Supabase and checks it is the same person."""
	try:
		auth_response = supabase.auth.sign_in_with_id_token({"provider": "google", "token": id_token})
	except AuthError as e:
		logger.exception("Supabase Auth failed during Google ID-token sign-in.")
		raise GoogleCredentialException("Supabase Auth could not establish a session.") from e
	if auth_response.session is None or auth_response.user is None:
		raise GoogleCredentialException("Supabase Auth did not return a valid session.")
	user = auth_response.user
	if not user.email or user.email.lower() != email or user.email_confirmed_at is None:
		raise GoogleIdentityException("Supabase Auth identity did not match the verified Google account.")
	return auth_response.session


def profile_id_for(user_supabase: Client, name: str | None, email: str) -> str:
	"""The student's profile id, creating the profile on a first sign-in."""
	try:
		result = user_supabase.rpc(
			"get_or_create_current_profile",
			{"profile_name": (name or "").strip() or email.partition("@")[0]},
		).execute()
	except APIError as e:
		if e.code == "P0001":  # an existing profile that only an administrator may link
			raise SignInRefused("account_link_required") from e
		raise
	profile_id = result.data
	if not isinstance(profile_id, str) or not profile_id:
		raise GoogleIdentityException("Could not load the application user profile.")
	return profile_id


def save_refresh_token(user_supabase: Client, profile_id: str, credentials: Credentials) -> None:
	"""Keeps the (encrypted) Google refresh token the backend needs to write Calendar events later."""
	try:
		encrypted = _refresh_token_to_store(user_supabase, profile_id, credentials)
	except GoogleRefreshConsentException as e:
		raise SignInRefused("calendar_consent_required") from e
	store_refresh_token(user_supabase, encrypted)


def _refresh_token_to_store(supabase: Client, profile_id: str, credentials: Credentials) -> str:
	"""Google only sends a refresh token on a fresh consent; otherwise the stored one stays in use."""
	if credentials.refresh_token:
		return encrypt_refresh_token(credentials.refresh_token)
	stored = load_refresh_token(supabase, profile_id, _backend_rpc_secret())
	if stored is None:
		raise GoogleRefreshConsentException()
	return stored


def _backend_rpc_secret() -> str:
	if not settings.SUPABASE_BACKEND_RPC_SECRET:
		raise GoogleCredentialException("Backend Supabase RPC authorization is not configured.")
	return settings.SUPABASE_BACKEND_RPC_SECRET
