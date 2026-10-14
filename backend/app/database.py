from typing import Annotated, Generator

from fastapi import Cookie, Depends
from supabase import Client, ClientOptions, create_client

from app.config import settings


def create_supabase_client(access_token: str | None = None) -> Client:
	options = ClientOptions(
		headers=(
			{"Authorization": f"Bearer {access_token}"}
			if access_token
			else {}
		),
		auto_refresh_token=False,
		persist_session=False,
	)
	return create_client(
		settings.SUPABASE_URL,
		settings.SUPABASE_KEY,
		options=options,
	)


def get_db(
	access_token: str | None = Cookie(default=None, alias="access_token"),
) -> Generator[Client, None, None]:
	yield create_supabase_client(access_token)


def get_public_db() -> Generator[Client, None, None]:
	yield create_supabase_client()


SupabaseClient = Annotated[Client, Depends(get_db)]
PublicSupabaseClient = Annotated[Client, Depends(get_public_db)]
