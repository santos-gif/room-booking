from typing import Any

from pydantic import BaseModel, ConfigDict


class GoogleIdentity(BaseModel):
	sub: str
	email: str | None = None
	email_verified: bool = False
	name: str | None = None
	# Workspace domain Google vouches for; absent for ordinary Google accounts.
	hd: str | None = None


class GoogleCalendarEvent(BaseModel):
	model_config = ConfigDict(extra="allow")

	id: str | None = None
	summary: str | None = None
	description: str | None = None
	location: str | None = None
	htmlLink: str | None = None
	start: dict[str, Any] | None = None
	end: dict[str, Any] | None = None

__all__ = [
	"GoogleCalendarEvent",
	"GoogleIdentity",
]
