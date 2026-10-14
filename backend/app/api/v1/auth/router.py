from fastapi import APIRouter, Cookie, Depends, Response
from starlette.concurrency import run_in_threadpool

from app.api.v1.auth.helper import (
	get_current_user,
	renew_tokens,
	save_onboarding,
)
from app.api.v1.auth.types import (
	AuthenticatedUser,
	OnboardingPayload,
	TokenRefreshResponse,
	UserResponse,
)
from app.api.v1.auth.helper import set_token_cookies
from app.database import PublicSupabaseClient, SupabaseClient

router = APIRouter(prefix="/auth")

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
	response: Response,
	supabase: PublicSupabaseClient,
	refresh_token: str | None = Cookie(default=None),
) -> TokenRefreshResponse:
	access_token, new_refresh_token, expires_in = await run_in_threadpool(
		renew_tokens, refresh_token, supabase
	)
	set_token_cookies(response, access_token, new_refresh_token, expires_in)
	return TokenRefreshResponse(
		message="Access and refresh tokens renewed."
	)


@router.get("/me", response_model=UserResponse)
async def get_me(
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserResponse:
	return UserResponse(
		**current_user.model_dump(),
		onboarding_complete=(
			current_user.nim is not None and current_user.major is not None
		),
	)


@router.post("/onboarding", response_model=UserResponse)
async def complete_onboarding(
	payload: OnboardingPayload,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserResponse:
	user = await run_in_threadpool(
		save_onboarding, supabase, current_user, payload
	)
	return UserResponse(**user.model_dump(), onboarding_complete=True)
