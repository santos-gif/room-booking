"""Cancelling a booking: its Google event first, then the database row, which is deleted right away."""
import logging

from postgrest.exceptions import APIError
from supabase import Client

from app.api.v1.appointment.exceptions import (
	AppointmentNotFoundException,
	AppointmentStorageException,
	CalendarSyncException,
)
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import GoogleCalendarOperationException
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)


def get_own_appointment(
	supabase: Client,
	appointment_id: str,
	current_user: AuthenticatedUser,
) -> dict[str, object]:
	appointment = appointment_queries.get_own(supabase, appointment_id, current_user.id)
	if appointment is None:
		raise AppointmentNotFoundException()
	return appointment


def cancel_appointment(
	appointment_id: str,
	supabase: Client,
	current_user: AuthenticatedUser,
) -> None:
	appointment = get_own_appointment(supabase, appointment_id, current_user)
	calendar_id = appointment.get("google_calendar_id")
	event_id = appointment.get("google_event_id")
	if isinstance(calendar_id, str) and isinstance(event_id, str):
		try:
			delete_calendar_event(calendar_id, event_id)
		except GoogleCalendarOperationException as error:
			logger.exception("Could not delete the room calendar event.")
			raise CalendarSyncException() from error
	try:
		updated_data = appointment_queries.update_own_state(
			supabase, appointment_id, "cancelled", "synced"
		)
	except APIError as error:
		logger.exception("Google event was deleted but booking cancellation failed.")
		raise CalendarSyncException() from error
	if not updated_data:
		raise AppointmentStorageException()
	# A cancelled booking should leave no trace. Best effort: if this fails (or a reschedule still points
	# at it) the row stays cancelled, invisible and bookable-around, until the daily purge removes it.
	try:
		appointment_queries.remove_own_cancelled(supabase, appointment_id)
	except Exception:  # noqa: BLE001 - the booking is cancelled; the daily purge removes the leftover row
		logger.exception("Could not delete cancelled appointment %s now.", appointment_id)
