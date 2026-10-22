from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Major = Literal[
	"Information Technology",
	"Management",
	"Culinary Arts",
	"Visual Communication Design",
	"Accounting",
	"Architecture",
	"Business Information System",
	"Civil Engineering",
	"Hospitality & Tourism",
	"Interior Design",
	"Urban Planning",
]


class TokenRefreshResponse(BaseModel):
	message: str


class AuthenticatedUser(BaseModel):
	model_config = ConfigDict(extra="forbid")

	id: str
	email: str
	name: str | None = None
	nim: int | None = None
	major: str | None = None


class OnboardingPayload(BaseModel):
	model_config = ConfigDict(extra="forbid")

	# Capped below 2^53: JavaScript loses integer precision above that. Fits Postgres bigint.
	nim: StrictInt = Field(gt=0, le=9_999_999_999_999)
	major: Major


class UserResponse(AuthenticatedUser):
	onboarding_complete: bool

__all__ = [
	"AuthenticatedUser",
	"OnboardingPayload",
	"TokenRefreshResponse",
	"UserResponse",
]