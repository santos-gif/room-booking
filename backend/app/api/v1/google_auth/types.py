from typing import Any

from pydantic import BaseModel, ConfigDict


class GoogleIdentity(BaseModel):
	email: str | None = None
	email_verified: bool = False


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
