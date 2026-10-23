"""The Google Calendar event of a freshly reserved booking, and what happens when it cannot be made."""
import logging

from fastapi import Response
from supabase import Client

from app.api.v1.appointment.exceptions import CalendarAccessException, CalendarSyncException
from app.api.v1.appointment.rollback import discard_pending_booking, mark_failed
from app.google_api.calendar_api import create_calendar_event
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarAccessException,
	GoogleCalendarOperationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
)

logger = logging.getLogger(__name__)


def create_event_or_roll_back(
	supabase: Client,
	user_id: str,
	appointment_id: str,
	calendar_id: str,
	event_id: str,
	event_body: dict[str, object],
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> None:
	"""Creates the event for a pending booking. On any failure the slot is never left held as pending."""
	try:
		create_calendar_event(
			supabase, user_id, calendar_id, event_id, event_body, access_token, expires_at, response
		)
	except (GoogleAuthorizationException, GoogleRefreshTokenException, GoogleCredentialException):
		# No stored token or broken credentials: release the slot.
		discard_pending_booking(supabase, appointment_id)
		raise
	except GoogleCalendarOperationException as error:
		logger.exception("Google Calendar event creation failed.")
		_undo_possibly_created_event(
			supabase, user_id, appointment_id, calendar_id, event_id, access_token, expires_at, response
		)
		if isinstance(error, GoogleCalendarAccessException):
			raise CalendarAccessException() from error
		raise CalendarSyncException() from error
	except Exception:
		# Anything unexpected (transport error, undecryptable token).
		logger.exception("Calendar event creation crashed.")
		discard_pending_booking(supabase, appointment_id)
		raise


def _undo_possibly_created_event(
	supabase: Client,
	user_id: str,
	appointment_id: str,
	calendar_id: str,
	event_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> None:
	"""A timeout may hide a created event, so delete it too (a missing event is fine), then release the slot."""
	try:
		delete_calendar_event(supabase, user_id, calendar_id, event_id, access_token, expires_at, response)
	except (GoogleAuthorizationException, GoogleCalendarOperationException):
		# The event may exist: keep the row for reconciliation instead of losing track of it.
		logger.exception("Could not remove a possibly created event.")
		mark_failed(supabase, appointment_id)
	else:
		discard_pending_booking(supabase, appointment_id)
