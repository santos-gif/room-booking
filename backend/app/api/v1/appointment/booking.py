"""Listing, creating and cancelling bookings (each one mirrored as a Google Calendar event)."""
import logging
from datetime import timedelta, timezone
from uuid import uuid4

from fastapi import Response
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
from app.api.v1.appointment.rollback import discard_pending_booking, mark_failed
from app.api.v1.appointment.slots import _booker_name, _calendar_event, _responses, _validate_slot
from app.api.v1.appointment.types import AppointmentPayload, AppointmentResponse
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_api import create_calendar_event, room_calendar_id
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
)
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)


def list_appointments(
	supabase: Client,
	current_user: AuthenticatedUser,
) -> list[AppointmentResponse]:
	return _responses(appointment_queries.list_active(supabase, current_user.id))


def create_appointment(
	payload: AppointmentPayload,
	supabase: Client,
	current_user: AuthenticatedUser,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
	replaces_appointment_id: str | None = None,
) -> AppointmentResponse:
	start_time = _validate_slot(payload.start_time, payload.room_number)
	if current_user.nim is None:
		raise ProfileIncompleteException()
	name = _booker_name(current_user)
	end_time = start_time + timedelta(hours=1)
	calendar_id = room_calendar_id(payload.room_number)
	appointment_id = str(uuid4())
	event_id = uuid4().hex
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
	rows = _responses(created)
	if len(rows) != 1:
		raise AppointmentStorageException()
	try:
		create_calendar_event(
			supabase,
			current_user.id,
			calendar_id,
			event_id,
			_calendar_event(
				appointment_id, payload.room_number, start_time, end_time, name, current_user.nim
			),
			access_token,
			expires_at,
			response,
		)
	except (GoogleAuthorizationException, GoogleRefreshTokenException, GoogleCredentialException):
		# No stored token or broken credentials: release the slot instead of holding it pending.
		discard_pending_booking(supabase, appointment_id)
		raise
	except GoogleCalendarOperationException as error:
		logger.exception("Google Calendar event creation failed.")
		# A timeout may hide a created event, so remove it too (a missing event is fine).
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
		except (GoogleAuthorizationException, GoogleCalendarOperationException):
			logger.exception("Could not remove a possibly created event.")
			mark_failed(supabase, appointment_id)
		else:
			discard_pending_booking(supabase, appointment_id)
		raise CalendarSyncException() from error
	except Exception:
		# Anything unexpected (transport error, undecryptable token): never leave the slot held pending.
		logger.exception("Calendar event creation crashed.")
		discard_pending_booking(supabase, appointment_id)
		raise
	try:
		updated_data = appointment_queries.update_own_state(
			supabase, appointment_id, "confirmed", "synced"
		)
	except APIError as error:
		logger.exception("Calendar event exists but booking confirmation failed.")
		raise CalendarSyncException() from error
	rows = _responses(updated_data)
	if len(rows) != 1:
		raise CalendarSyncException()
	return rows[0]
