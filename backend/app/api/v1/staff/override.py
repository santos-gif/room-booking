"""Taking one slot for staff: whoever holds it is cancelled (and told), the slot becomes a staff booking."""
import logging
from datetime import datetime
from uuid import uuid4

from supabase import Client

from app.api.v1.appointment.calendar_event import booker_name, build_staff_hold_event
from app.api.v1.appointment.exceptions import (
	AppointmentStorageException,
	CalendarAccessException,
	CalendarSyncException,
)
from app.api.v1.appointment.slots import SLOT_LENGTH, to_responses, validate_slot
from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.staff.access import staff_db_errors
from app.api.v1.staff.closures import to_staff_bookings
from app.api.v1.staff.events import remove_events
from app.api.v1.staff.types import OverridePayload, OverrideResult, StaffBooking
from app.google_api.calendar_api import create_calendar_event, room_calendar_id
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import GoogleCalendarAccessException, GoogleCalendarOperationException
from app.queries import appointments as appointment_queries
from app.queries import staff as staff_queries

logger = logging.getLogger(__name__)


def holder(supabase: Client, room_number: int, start_time: datetime) -> list[StaffBooking]:
	"""Who holds this slot right now (empty if it is free)."""
	start = validate_slot(start_time, room_number, staff=True)
	with staff_db_errors():
		return to_staff_bookings(staff_queries.list_bookings(supabase, room_number, start, start + SLOT_LENGTH, False))


def override(supabase: Client, staff: AuthenticatedUser, payload: OverridePayload) -> OverrideResult:
	"""The hold's Google event is made FIRST: if the calendar cannot be written, nobody has been cancelled yet."""
	start = validate_slot(payload.start_time, payload.room_number, staff=True)
	calendar_id = room_calendar_id(payload.room_number)
	event_id, hold_id = uuid4().hex, str(uuid4())
	body = build_staff_hold_event(
		hold_id, payload.room_number, start, start + SLOT_LENGTH, booker_name(staff), payload.reason
	)
	try:
		create_calendar_event(calendar_id, event_id, body)
	except GoogleCalendarAccessException as error:
		raise CalendarAccessException() from error
	except GoogleCalendarOperationException as error:
		raise CalendarSyncException() from error
	try:
		with staff_db_errors():
			rows = staff_queries.override_slot(
				supabase, payload.room_number, start, payload.reason, calendar_id, event_id, hold_id
			)
	except Exception:
		_remove_quietly(calendar_id, event_id)  # nothing was cancelled, so the new event must not stay
		raise
	cancelled = [row for row in rows if row.get("status") == "cancelled"]
	if not any(row.get("id") == hold_id for row in rows):
		raise AppointmentStorageException()
	events_left = remove_events(supabase, cancelled)
	confirmed = to_responses(appointment_queries.update_own_state(supabase, hold_id, "confirmed", "synced"))
	if len(confirmed) != 1:
		raise CalendarSyncException()
	return OverrideResult(cancelled=len(cancelled), events_left=events_left, appointment=confirmed[0])


def _remove_quietly(calendar_id: str, event_id: str) -> None:
	try:
		delete_calendar_event(calendar_id, event_id)
	except GoogleCalendarOperationException:
		logger.exception("Could not remove the staff hold event %s after a failed override.", event_id)
