import base64
import json
from datetime import datetime, timedelta, timezone

from fastapi import Cookie
from fastapi import HTTPException
from postgrest.exceptions import APIError
from pydantic import TypeAdapter, ValidationError
from supabase import Client
from supabase_auth.errors import AuthError

from app.api.v1.auth.exceptions import CredentialsException, UserNotFoundException
from app.api.v1.auth.types import AuthenticatedUser, OnboardingPayload
from app.cookies import ACCESS_COOKIE
from app.database import SupabaseClient
from app.models.user import UserRecord

USER_RECORDS = TypeAdapter(list[UserRecord])


# A session is renewed for at most this long after the real Google sign-in, so a student removed from the
# Workspace is cut off within a week. Placeholder: tune after real testing (decisions/auth.md).
MAX_SESSION_AGE = timedelta(days=7)


def _signed_in_at(access_token: str) -> datetime | None:
	"""When the student really signed in, from the signed `amr` claim Supabase keeps through renewals."""
	try:
		claims = json.loads(base64.urlsafe_b64decode(access_token.split(".")[1] + "==="))
		stamps = [int(entry["timestamp"]) for entry in claims.get("amr", [])]
	except (IndexError, ValueError, TypeError, KeyError, AttributeError):
		return None  # shortcut: no usable claim means no cap rather than a lockout; verify with a real token
	return datetime.fromtimestamp(max(stamps), timezone.utc) if stamps else None


def renew_tokens(
	refresh_token: str | None,
	supabase: Client,
) -> tuple[str, str, int]:
	if not refresh_token:
		raise CredentialsException()
	try:
		auth_response = supabase.auth.refresh_session(refresh_token=refresh_token)
	except AuthError as error:
		raise CredentialsException() from error
	if auth_response.session is None:
		raise CredentialsException()
	session = auth_response.session
	signed_in_at = _signed_in_at(session.access_token)
	if signed_in_at and datetime.now(timezone.utc) - signed_in_at > MAX_SESSION_AGE:
		raise CredentialsException()
	return session.access_token, session.refresh_token, session.expires_in


def get_current_user(
	supabase: SupabaseClient,
	access_token: str | None = Cookie(None, alias=ACCESS_COOKIE),
) -> AuthenticatedUser:
	if not access_token:
		raise CredentialsException()
	try:
		auth_response = supabase.auth.get_user(access_token)
	except AuthError as error:
		raise CredentialsException() from error
	if auth_response is None or auth_response.user is None:
		raise CredentialsException()

	try:
		profile_result = supabase.rpc("current_profile_id").execute()
	except APIError as error:
		# An expired or invalid JWT makes the RPC fail; that is a login problem, not a crash.
		raise CredentialsException() from error
	profile_id = profile_result.data
	if not isinstance(profile_id, str) or not profile_id:
		raise UserNotFoundException()
	result = (
		supabase.table("users")
		.select("*")
		.eq("id", profile_id)
		.limit(1)
		.execute()
	)
	try:
		users = USER_RECORDS.validate_python(result.data)
	except ValidationError as error:
		# e.g. a users row with a null email.
		raise UserNotFoundException() from error
	if len(users) != 1:
		raise UserNotFoundException()
	user = users[0]
	return AuthenticatedUser(
		id=user.id,
		email=user.email,
		name=user.name,
		nim=user.nim,
		major=user.major,
		role="staff" if user.role == "staff" else "student",
	)


def save_onboarding(
	supabase: SupabaseClient,
	current_user: AuthenticatedUser,
	payload: OnboardingPayload,
) -> AuthenticatedUser:
	try:
		result = (
			supabase.table("users")
			.update({"nim": payload.nim, "major": payload.major})
			.eq("id", current_user.id)
			.execute()
		)
	except APIError as error:
		if error.code == "23505":
			raise HTTPException(409, "That NIM/NIDN is already registered.") from error
		raise
	if not result.data or not isinstance(result.data[0], dict):
		raise UserNotFoundException()
	try:
		user = UserRecord.model_validate(result.data[0])
	except ValidationError as error:
		raise UserNotFoundException() from error
	return AuthenticatedUser(
		id=user.id,
		email=user.email,
		name=user.name,
		nim=user.nim,
		major=user.major,
		role="staff" if user.role == "staff" else "student",
	)
