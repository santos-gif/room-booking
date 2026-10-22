"""Make one confirmed-looking booking and its Google Calendar event agree."""
import logging
from datetime import datetime, timezone

from fastapi import Response
from postgrest.exceptions import APIError
from supabase import Client

from app.api.v1.appointment.slots import _calendar_event
from app.api.v1.appointment.types import JAKARTA_TZ
from app.google_api.calendar_api import create_calendar_event
from app.google_api.calendar_single_event import (
	get_calendar_event,
	update_calendar_event,
)
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
)
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)


def stored_utc(value: object) -> datetime | None:
	if not isinstance(value, str):
		return None
	try:
		parsed = datetime.fromisoformat(value)
	except ValueError:
		return None
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=timezone.utc)
	return parsed.astimezone(timezone.utc)


def _calendar_time_matches(event: dict[str, object], field: str, expected: object) -> bool:
	event_time = event.get(field)
	if not isinstance(event_time, dict):
		return False
	actual = stored_utc(event_time.get("dateTime"))
	target = stored_utc(expected)
	return actual is not None and target is not None and actual == target


def sync_row(supabase: Client, row: dict[str, object]) -> str:
	"""Make Google match the row. Returns "synchronized", "released" or "failed"."""
	appointment_id = row.get("id")
	user_id = row.get("booker_id")
	calendar_id = row.get("google_calendar_id")
	event_id = row.get("google_event_id")
	room_number = row.get("room_number")
	if not (
		isinstance(appointment_id, str)
		and isinstance(user_id, str)
		and isinstance(calendar_id, str)
		and isinstance(event_id, str)
		and room_number in (1, 2)
	):
		logger.error("Appointment %r is missing calendar reconciliation data.", appointment_id)
		return "failed"
	# The row carries no name/NIM today, so these are normally None (see ARCHITECTURE.md).
	who = (row.get("name"), row.get("nim"))
	start_value = row.get("start_time")
	end_value = row.get("end_time")
	try:
		event = get_calendar_event(supabase, user_id, calendar_id, event_id, None, None, Response())
		if event is None or event.get("status") == "cancelled":
			if event is None and row.get("sync_status") in ("pending", "failed"):
				event = create_calendar_event(
					supabase,
					user_id,
					calendar_id,
					event_id,
					_calendar_event(
						appointment_id,
						room_number,
						datetime.fromisoformat(row["start_time"]).astimezone(JAKARTA_TZ),
						datetime.fromisoformat(row["end_time"]).astimezone(JAKARTA_TZ),
						*who,
					),
					None,
					None,
					Response(),
				)
			else:
				appointment_queries.update_for_reconciliation(
					supabase, appointment_id, "cancelled", "synced"
				)
				return "released"
		if event is None:
			raise GoogleCalendarOperationException()
		if not _calendar_time_matches(event, "start", start_value) or not _calendar_time_matches(
			event, "end", end_value
		):
			start = datetime.fromisoformat(str(start_value)).astimezone(JAKARTA_TZ)
			end = datetime.fromisoformat(str(end_value)).astimezone(JAKARTA_TZ)
			body = _calendar_event(appointment_id, room_number, start, end, *who)
			if not all(who):
				# update is a full replace: keep the title the booking was created with.
				body["summary"] = event.get("summary") or body["summary"]
			update_calendar_event(
				supabase,
				user_id,
				calendar_id,
				event_id,
				body,
				None,
				None,
				Response(),
			)
		appointment_queries.update_for_reconciliation(supabase, appointment_id, "confirmed", "synced")
		row["status"] = "confirmed"
		row["sync_status"] = "synced"
		return "synchronized"
	except (
		GoogleAuthorizationException,
		GoogleCalendarOperationException,
		GoogleCredentialException,
		GoogleRefreshTokenException,
		APIError,
	):
		logger.exception("Appointment %s could not be reconciled.", appointment_id)
		return "failed"
