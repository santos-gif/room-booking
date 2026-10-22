import logging

from fastapi import Response
from postgrest.exceptions import APIError
from supabase import Client

from app.api.v1.appointment.exceptions import (
	AppointmentNotFoundException,
	AppointmentStorageException,
	CalendarSyncException,
)
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
)
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
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> None:
	appointment = get_own_appointment(supabase, appointment_id, current_user)
	calendar_id = appointment.get("google_calendar_id")
	event_id = appointment.get("google_event_id")
	if isinstance(calendar_id, str) and isinstance(event_id, str):
		try:
			delete_calendar_event(
				supabase,
				current_user.id,
				calendar_id,
				event_id,
				access_token,
				expires_at,
				response,
			)
		except GoogleAuthorizationException:
			raise
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
