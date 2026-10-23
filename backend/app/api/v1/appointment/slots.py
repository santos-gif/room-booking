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
OPEN_HOUR, CLOSE_HOUR = 8, 17  # slots start on the hour from OPEN_HOUR; the last one ends at CLOSE_HOUR
SLOT_LENGTH = timedelta(hours=1)
LEAD = timedelta(minutes=5)
# Same limit as the database trigger (appointments_booking_window).
MAX_ADVANCE = timedelta(days=90)
APPOINTMENTS_ADAPTER = TypeAdapter(list[AppointmentRecord])


def to_responses(data: object) -> list[AppointmentResponse]:
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


def validate_slot(start_time: datetime, room_number: int) -> datetime:
	local_start = start_time.astimezone(JAKARTA_TZ)
	if room_number not in (1, 2):
		raise AppointmentValidationException("Choose Discussion Room 1 or 2.")
	if (
		local_start.weekday() > 4
		or not OPEN_HOUR <= local_start.hour < CLOSE_HOUR
		or local_start.minute != 0
		or local_start.second != 0
		or local_start.microsecond != 0
	):
		raise AppointmentValidationException(
			f"Bookings must start on weekdays between {OPEN_HOUR:02d}:00 and {CLOSE_HOUR - 1:02d}:00 WIB."
		)
	now = datetime.now(JAKARTA_TZ)
	if local_start <= now + LEAD:
		raise AppointmentValidationException(
			f"Bookings close {LEAD.seconds // 60} minutes before the slot starts."
		)
	if local_start > now + MAX_ADVANCE:
		raise AppointmentValidationException(f"Bookings open at most {MAX_ADVANCE.days} days ahead.")
	return local_start


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
			end_time=slot + SLOT_LENGTH,
			available=(
				booking_date.weekday() < 5
				and slot not in booked_starts
				and now + LEAD < slot <= now + MAX_ADVANCE
				and bookings_used < MAX_ACTIVE_BOOKINGS
			),
		)
		for hour in range(OPEN_HOUR, CLOSE_HOUR)
		for slot in [datetime.combine(booking_date, time(hour), tzinfo=JAKARTA_TZ)]
	]
	return AvailabilityResponse(
		bookings_used=bookings_used,
		bookings_remaining=max(0, MAX_ACTIVE_BOOKINGS - bookings_used),
		slots=slots,
	)

