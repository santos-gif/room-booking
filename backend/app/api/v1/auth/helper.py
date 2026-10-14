from typing import Any

from fastapi import Cookie
from fastapi.responses import Response
from pydantic import TypeAdapter
from supabase import Client
from supabase_auth.errors import AuthError

from app.api.v1.auth.exceptions import CredentialsException, UserNotFoundException
from app.api.v1.auth.types import AuthenticatedUser, OnboardingPayload
from app.config import settings
from app.database import SupabaseClient
from app.models.user import UserRecord

USER_RECORDS = TypeAdapter(list[UserRecord])
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def set_token_cookies(
	response: Response,
	access_token: str,
	refresh_token: str,
	access_max_age: int = 3600,
) -> None:
	cookie_options: dict[str, Any] = {
		"httponly": True,
		"secure": settings.COOKIE_SECURE,
		"samesite": settings.COOKIE_SAMESITE,
		"path": "/",
	}
	response.set_cookie(
		key="access_token",
		value=access_token,
		max_age=max(0, access_max_age),
		**cookie_options,
	)
	response.set_cookie(
		key="refresh_token",
		value=refresh_token,
		max_age=REFRESH_COOKIE_MAX_AGE,
		**cookie_options,
	)


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
	return session.access_token, session.refresh_token, session.expires_in


def get_current_user(
	supabase: SupabaseClient,
	access_token: str | None = Cookie(None, alias="access_token"),
) -> AuthenticatedUser:
	if not access_token:
		raise CredentialsException()
	try:
		auth_response = supabase.auth.get_user(access_token)
	except AuthError as error:
		raise CredentialsException() from error
	if auth_response is None or auth_response.user is None:
		raise CredentialsException()

	profile_result = supabase.rpc("current_profile_id").execute()
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
	users = USER_RECORDS.validate_python(result.data)
	if len(users) != 1:
		raise UserNotFoundException()
	user = users[0]
	return AuthenticatedUser(
		id=user.id,
		email=user.email,
		name=user.name,
		nim=user.nim,
		major=user.major,
	)


def save_onboarding(
	supabase: SupabaseClient,
	current_user: AuthenticatedUser,
	payload: OnboardingPayload,
) -> AuthenticatedUser:
	result = (
		supabase.table("users")
		.update({"nim": payload.nim, "major": payload.major})
		.eq("id", current_user.id)
		.execute()
	)
	if not result.data or not isinstance(result.data[0], dict):
		raise UserNotFoundException()
	user = UserRecord.model_validate(result.data[0])
	return AuthenticatedUser(
		id=user.id,
		email=user.email,
		name=user.name,
		nim=user.nim,
		major=user.major,
	)
