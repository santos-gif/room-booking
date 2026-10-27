"""After Google says who the student is: their Supabase session and their profile."""
import logging

from postgrest.exceptions import APIError
from supabase import Client
from supabase_auth.errors import AuthError
from supabase_auth.types import Session

from app.api.v1.google_auth.callback_identity import SignInRefused
from app.google_api.exceptions import GoogleCredentialException, GoogleIdentityException

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

