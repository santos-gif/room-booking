"""Listing, creating and cancelling bookings (each one mirrored as a Google Calendar event)."""
import logging
from datetime import timedelta, timezone
from uuid import uuid4

from postgrest.exceptions import APIError
from postgrest.types import JSON
from supabase import Client

from app.api.v1.appointment.exceptions import (
	AppointmentConflictException,
	AppointmentNotFoundException,
	AppointmentStorageException,
	AppointmentValidationException,
	CalendarSyncException,
	DailyBookingLimitException,
	ProfileIncompleteException,
)
from app.api.v1.appointment.booking_event import create_event_or_roll_back
from app.api.v1.appointment.calendar_event import booker_name, build_calendar_event
from app.api.v1.appointment.slots import to_responses, validate_slot
from app.api.v1.appointment.types import AppointmentPayload, AppointmentResponse
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_api import room_calendar_id
from app.queries import appointments as appointment_queries
from app.queries import staff as staff_queries

logger = logging.getLogger(__name__)


def list_appointments(
	supabase: Client,
	current_user: AuthenticatedUser,
) -> list[AppointmentResponse]:
	return to_responses(appointment_queries.list_active(supabase, current_user.id))


def create_appointment(
	payload: AppointmentPayload,
	supabase: Client,
	current_user: AuthenticatedUser,
	replaces_appointment_id: str | None = None,
) -> AppointmentResponse:
	"""Reserve the slot (a pending row), mirror it in Google Calendar, then confirm it."""
	start_time = validate_slot(payload.start_time, payload.room_number, staff=current_user.role == "staff")
	if current_user.nim is None:
		raise ProfileIncompleteException()
	closure = staff_queries.closure_on(supabase, payload.room_number, start_time.date())
	if closure:
		raise AppointmentValidationException(f"The room is closed on that date: {closure['reason']}")
	end_time = start_time + timedelta(hours=1)
	calendar_id = room_calendar_id(payload.room_number)
	appointment_id = str(uuid4())
	event_id = uuid4().hex
	event_body = build_calendar_event(
		appointment_id, payload.room_number, start_time, end_time, booker_name(current_user), current_user.nim
	)
	values: JSON = {
		"id": appointment_id,
		"booker_id": current_user.id,
		"room_number": payload.room_number,
		"start_time": start_time.astimezone(timezone.utc).isoformat(),
		"end_time": end_time.astimezone(timezone.utc).isoformat(),
		"google_calendar_id": calendar_id,
		"google_event_id": event_id,
		"status": "pending",
		"sync_status": "pending",
	}
	if replaces_appointment_id:
		values["replaces_appointment_id"] = replaces_appointment_id
	_reserve_slot(supabase, values, replaces_appointment_id)
	create_event_or_roll_back(supabase, appointment_id, calendar_id, event_id, event_body)
	return _confirm(supabase, appointment_id)


def _reserve_slot(supabase: Client, values: JSON, replaces_appointment_id: str | None) -> None:
	"""Inserts the pending row; the database's constraints decide who gets a contested slot."""
	try:
		created = appointment_queries.insert(supabase, values)
	except APIError as error:
		if error.code in ("23P01", "23505"):
			raise AppointmentConflictException() from error
		if error.code == "P0001":
			raise DailyBookingLimitException() from error
		if replaces_appointment_id and error.code in ("23514", "23503"):
			# The old booking was cancelled between the lookup and this insert.
			raise AppointmentNotFoundException() from error
		if error.code == "23514":  # the database's own booking-window rule, a moment after ours
			raise AppointmentValidationException("That time can no longer be booked.") from error
		logger.exception("Database rejected appointment reservation.")
		raise AppointmentStorageException() from error
	if len(to_responses(created)) != 1:
		raise AppointmentStorageException()


def _confirm(supabase: Client, appointment_id: str) -> AppointmentResponse:
	"""The event exists: turn the pending row into a confirmed one."""
	try:
		updated_data = appointment_queries.update_own_state(supabase, appointment_id, "confirmed", "synced")
	except APIError as error:
		logger.exception("Calendar event exists but booking confirmation failed.")
		raise CalendarSyncException() from error
	rows = to_responses(updated_data)
	if len(rows) != 1:
		raise CalendarSyncException()
	return rows[0]
