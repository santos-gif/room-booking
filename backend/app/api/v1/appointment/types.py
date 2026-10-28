from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, StrictInt, field_validator

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


class AppointmentPayload(BaseModel):
	model_config = ConfigDict(extra="forbid")

	room_number: StrictInt
	start_time: datetime

	@field_validator("room_number")
	@classmethod
	def ensure_valid_room(cls, value: int) -> int:
		if value not in (1, 2):
			raise ValueError("Choose Discussion Room 1 or 2.")
		return value

	@field_validator("start_time")
	@classmethod
	def ensure_jakarta_timezone(cls, value: datetime) -> datetime:
		try:
			if value.tzinfo is None:
				return value.replace(tzinfo=JAKARTA_TZ)
			return value.astimezone(JAKARTA_TZ)
		except OverflowError as error:  # e.g. year 1 or 9999 with an offset: a clean 422, not a 500
			raise ValueError("Choose a valid date and time.") from error


class AvailableSlot(BaseModel):
	start_time: datetime
	end_time: datetime
	available: bool


class AvailabilityResponse(BaseModel):
	bookings_used: int
	bookings_remaining: int
	slots: list[AvailableSlot]
	closed_reason: str | None = None


class ReschedulePayload(AppointmentPayload):
	pass


class AppointmentResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	id: str
	booker_id: str
	room_number: Literal[1, 2]
	start_time: datetime
	end_time: datetime
	status: str
	sync_status: str

	@field_validator("start_time", "end_time")
	@classmethod
	def convert_to_jakarta_timezone(cls, value: datetime) -> datetime:
		if value.tzinfo is None:
			return value.replace(tzinfo=JAKARTA_TZ)
		return value.astimezone(JAKARTA_TZ)


class NoticeResponse(BaseModel):
	"""A message for a student whose booking staff cancelled, shown in My bookings until dismissed."""

	id: str
	message: str
	created_at: datetime


class ReconciliationResponse(BaseModel):
	checked: int
	synchronized: int
	released: int
	failed: int
	purged: int = 0


__all__ = [
	"AppointmentPayload",
	"AppointmentResponse",
	"ReschedulePayload",
	"AvailabilityResponse",
	"AvailableSlot",
	"NoticeResponse",
	"ReconciliationResponse",
]
