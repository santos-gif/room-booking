"""Slot rules shared by the booking files: validation, availability, response shapes."""
from datetime import date, datetime, time, timedelta
from typing import Literal, cast

from pydantic import TypeAdapter, ValidationError
from supabase import Client

from app.api.v1.appointment.exceptions import (
	AppointmentNotFoundException,
	AppointmentStorageException,
	AppointmentValidationException,
)
from app.api.v1.appointment.types import (
	AppointmentResponse,
	AvailabilityResponse,
	AvailableSlot,
	JAKARTA_TZ,
)
from app.api.v1.auth.types import AuthenticatedUser
from app.models.appointment import AppointmentRecord
from app.queries import appointments as appointment_queries

# Mirrors the database trigger enforce_active_booking_limit.
MAX_ACTIVE_BOOKINGS = 3
# A slot closes this long before it starts.
LEAD = timedelta(minutes=5)
APPOINTMENTS_ADAPTER = TypeAdapter(list[AppointmentRecord])


def _responses(data: object) -> list[AppointmentResponse]:
	try:
		records = APPOINTMENTS_ADAPTER.validate_python(data or [])
		return [
			AppointmentResponse(
				id=record.id,
				booker_id=record.booker_id,
				room_number=cast(Literal[1,2], record.room_number),
				start_time=record.start_time,
				end_time=record.end_time,
				status=record.status,
				sync_status=record.sync_status,
			)
			for record in records
		]
	except ValidationError as error:
		raise AppointmentStorageException() from error


def _validate_slot(start_time: datetime, room_number: int) -> datetime:
	local_start = start_time.astimezone(JAKARTA_TZ)
	if room_number not in (1, 2):
		raise AppointmentValidationException("Choose Discussion Room 1 or 2.")
	if (
		local_start.weekday() > 4
		or not 8 <= local_start.hour < 17
		or local_start.minute != 0
		or local_start.second != 0
		or local_start.microsecond != 0
	):
		raise AppointmentValidationException(
			"Bookings must start on weekdays between 08:00 and 16:00 WIB."
		)
	if local_start <= datetime.now(JAKARTA_TZ) + LEAD:
		raise AppointmentValidationException("Bookings close 5 minutes before the slot starts.")
	return local_start


def _calendar_event(
	appointment_id: str,
	room_number: int,
	start_time: datetime,
	end_time: datetime,
	name: str | None = None,
	nim: int | None = None,
) -> dict[str, object]:
	# Without a name and NIM (reconcile rows do not carry them) fall back to the room only.
	title = f"Discussion Room {room_number}"
	if name and nim is not None:
		title = f"{title}-{name} ({nim})"
	return {
		"summary": title,
		"description": f"Room booking appointment ID: {appointment_id}",
		"start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Jakarta"},
		"end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Jakarta"},
	}


def get_availability(
	supabase: Client,
	booking_date: date,
	room_number: int,
	current_user: AuthenticatedUser,
	exclude_appointment_id: str | None = None,
) -> AvailabilityResponse:
	if room_number not in (1, 2):
		raise AppointmentValidationException("Choose Discussion Room 1 or 2.")
	if exclude_appointment_id and not appointment_queries.get_own(
		supabase, exclude_appointment_id, current_user.id
	):
		raise AppointmentNotFoundException()
	data = appointment_queries.availability(supabase, booking_date, room_number, exclude_appointment_id)
	if not data or not isinstance(data, list) or not isinstance(data[0], dict):
		raise AppointmentStorageException()
	availability = data[0]
	raw_booked_starts = availability.get("booked_starts")
	try:
		booked_starts = {
			datetime.fromisoformat(value).astimezone(JAKARTA_TZ)
			for value in raw_booked_starts
			if isinstance(value, str)
		} if isinstance(raw_booked_starts, list) else set()
	except ValueError as error:
		raise AppointmentStorageException() from error
	bookings_used = availability.get("bookings_used")
	if not isinstance(bookings_used, int):
		raise AppointmentStorageException()
	now = datetime.now(JAKARTA_TZ)
	slots = [
		AvailableSlot(
			start_time=slot,
			end_time=slot + timedelta(hours=1),
			available=(
				booking_date.weekday() < 5
				and slot not in booked_starts
				and slot > now + LEAD
				and bookings_used < MAX_ACTIVE_BOOKINGS
			),
		)
		for hour in range(8, 17)
		for slot in [datetime.combine(booking_date, time(hour), tzinfo=JAKARTA_TZ)]
	]
	return AvailabilityResponse(
		bookings_used=bookings_used,
		bookings_remaining=max(0, MAX_ACTIVE_BOOKINGS - bookings_used),
		slots=slots,
	)

