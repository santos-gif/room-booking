"""Supabase RPCs for the stored (encrypted) Google refresh token."""
from pydantic import TypeAdapter
from supabase import Client

from app.config import settings
from app.models.google_refresh_token import GoogleRefreshTokenRecord

TOKEN_RECORDS = TypeAdapter(list[GoogleRefreshTokenRecord])


def load_refresh_token(supabase: Client, profile_id: str, backend_secret: str) -> str | None:
	"""Return the encrypted token, or None if there is none or it was invalidated.

	Each caller passes the secret and picks its own error, so they can differ.
	"""
	result = supabase.rpc(
		"get_google_refresh_token",
		{"requested_profile_id": profile_id, "backend_secret": backend_secret},
	).execute()
	rows = TOKEN_RECORDS.validate_python(result.data)
	if not rows or not rows[0].is_valid:
		return None
	return rows[0].refresh_token


def store_refresh_token(supabase: Client, encrypted_refresh_token: str) -> None:
	supabase.rpc(
		"store_google_refresh_token",
		{"token_value": encrypted_refresh_token},
	).execute()


def invalidate_refresh_token(supabase: Client, profile_id: str) -> None:
	supabase.rpc(
		"invalidate_google_refresh_token",
		{
			"requested_profile_id": profile_id,
			"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET,
		},
	).execute()
