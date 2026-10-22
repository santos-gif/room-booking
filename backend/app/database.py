from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from supabase import Client, ClientOptions, create_client

from app.config import settings


def create_supabase_client(access_token: str | None = None) -> Client:
	options = ClientOptions(
		headers=(
                        {"Authorization": f"Bearer {access_token}"} if access_token else {}
                        ),
		auto_refresh_token=False,
		persist_session=False,
	)

	return create_client(
		settings.SUPABASE_URL,
		settings.SUPABASE_KEY,
		options=options,
	)


def get_db(access_token: str | None = Cookie(default=None)) -> Client:
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    return create_supabase_client(access_token)


def get_public_db() -> Client:
    return create_supabase_client()


SupabaseClient = Annotated[Client, Depends(get_db)]
PublicSupabaseClient = Annotated[Client, Depends(get_public_db)]
