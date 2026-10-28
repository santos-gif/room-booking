from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.appointment.types import AppointmentPayload, AppointmentResponse

Reason = Field(min_length=1, max_length=200)


class ClosurePayload(BaseModel):
	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	room_number: Literal[1, 2]
	start_date: date
	end_date: date
	reason: str = Reason

	@model_validator(mode="after")
	def ensure_ordered_and_bounded(self) -> "ClosurePayload":
		if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
			raise ValueError("Choose an end date on or after the start date, at most one year apart.")
		return self


class OverridePayload(AppointmentPayload):
	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	reason: str = Reason


class StaffBooking(BaseModel):
	"""A booking staff are about to cancel, or the one holding a slot."""

	appointment_id: str
	booker_name: str | None
	booker_nim: int | None
	booker_email: str
	room_number: int
	start_time: datetime
	end_time: datetime


class ClosureResponse(BaseModel):
	id: str
	room_number: Literal[1, 2]
	start_date: date
	end_date: date
	reason: str


class StaffActionResult(BaseModel):
	cancelled: int
	events_left: int  # cancelled bookings whose Google event is not deleted yet (the nightly job finishes them)


class OverrideResult(StaffActionResult):
	appointment: AppointmentResponse


__all__ = [
	"ClosurePayload",
	"ClosureResponse",
	"OverridePayload",
	"OverrideResult",
	"StaffActionResult",
	"StaffBooking",
]
