from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Cookie
from fastapi.responses import Response
from pydantic import TypeAdapter

from app.api.v1.auth.exceptions import (
	CredentialsException,
	ExpiredAccessToken,
	ExpiredRefreshToken,
	UserNotFoundException,
)
from app.api.v1.auth.types import AuthenticatedUser, OnboardingPayload
from app.models.user import UserRecord
from app.config import settings
from app.database import SupabaseClient

USER_RECORDS = TypeAdapter(list[UserRecord])


def _email_pattern(email: str) -> str:
	return email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def verify_token(token: str) -> dict[str, Any]:
	return jwt.decode(
		token,
		settings.SECRET_ACCESS_TOKEN_JWT_KEY,
		algorithms=[settings.ALGORITHM],
	)


def create_tokens(user_email: str) -> tuple[str, str]:
	now_utc = datetime.now(timezone.utc)
	access_token_payload = {
		"sub": user_email,
		"exp": now_utc + timedelta(hours=1),
	}
	access_token = jwt.encode(
		access_token_payload,
		settings.SECRET_ACCESS_TOKEN_JWT_KEY,
		algorithm=settings.ALGORITHM,
	)
	refresh_token_payload = {
		"sub": user_email,
		"exp": now_utc + timedelta(days=30),
	}
	refresh_token = jwt.encode(
		refresh_token_payload,
		settings.SECRET_REFRESH_TOKEN_JWT_KEY,
		algorithm=settings.ALGORITHM,
	)
	return access_token, refresh_token


def set_token_cookies(response: Response, access_token: str, refresh_token: str) -> None:
	cookie_options: dict[str, object] = {
		"httponly": True,
		"secure": settings.COOKIE_SECURE,
		"samesite": settings.COOKIE_SAMESITE,
		"path": "/",
	}
	response.set_cookie(
		key="access_token",
		value=access_token,
		max_age=3600,
		**cookie_options,
	)
	response.set_cookie(
		key="refresh_token",
		value=refresh_token,
		max_age=30 * 24 * 60 * 60,
		**cookie_options,
	)


def renew_tokens(
	refresh_token: str | None,
	supabase: SupabaseClient,
) -> tuple[str, str]:
	if not refresh_token:
		raise CredentialsException()
	try:
		payload = jwt.decode(
			refresh_token,
			settings.SECRET_REFRESH_TOKEN_JWT_KEY,
			algorithms=[settings.ALGORITHM],
		)
	except jwt.ExpiredSignatureError as error:
		raise ExpiredRefreshToken() from error
	except jwt.PyJWTError as error:
		raise CredentialsException() from error

	email = payload.get("sub")
	if not isinstance(email, str) or not email:
		raise CredentialsException()
	result = (
		supabase.table("users")
		.select("id,email")
		.ilike("email", _email_pattern(email))
		.limit(2)
		.execute()
	)
	matches = [
		user
		for user in USER_RECORDS.validate_python(result.data)
		if user.email.casefold() == email.casefold()
	]
	if len(matches) != 1:
		raise UserNotFoundException()
	return create_tokens(user_email=email)


def get_current_user(
	supabase: SupabaseClient,
	access_token: str | None = Cookie(None),
) -> AuthenticatedUser:
	if not access_token:
		raise CredentialsException()
	try:
		payload = jwt.decode(
			access_token,
			settings.SECRET_ACCESS_TOKEN_JWT_KEY,
			algorithms=[settings.ALGORITHM],
		)
	except jwt.ExpiredSignatureError as error:
		raise ExpiredAccessToken() from error
	except jwt.PyJWTError as error:
		raise CredentialsException() from error

	email = payload.get("sub")
	if not isinstance(email, str) or not email:
		raise CredentialsException()
	result = (
		supabase.table("users")
		.select("*")
		.ilike("email", _email_pattern(email))
		.limit(2)
		.execute()
	)
	matches = [
		user
		for user in USER_RECORDS.validate_python(result.data)
		if user.email.casefold() == email.casefold()
	]
	if len(matches) != 1:
		raise UserNotFoundException()
	user = matches[0]
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
