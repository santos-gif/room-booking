"""After staff cancel bookings: delete their Google events, then tell the database which are done."""
import logging

from postgrest.exceptions import APIError
from supabase import Client

from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import GoogleCalendarOperationException
from app.queries import staff as staff_queries

logger = logging.getLogger(__name__)
# A request must not run for minutes (each delete is a Google call): the nightly job finishes the rest.
INLINE_LIMIT = 25


def remove_events(supabase: Client, cancelled: list[dict[str, object]]) -> int:
	"""Returns how many cancelled bookings still have their event. They stay `sync pending` for the nightly job."""
	removed: list[str] = []
	for row in cancelled[:INLINE_LIMIT]:
		calendar_id, event_id = row.get("google_calendar_id"), row.get("google_event_id")
		try:
			if isinstance(calendar_id, str) and isinstance(event_id, str):
				delete_calendar_event(calendar_id, event_id)
			removed.append(str(row["id"]))
		except GoogleCalendarOperationException:
			logger.exception("Could not delete the event of staff-cancelled appointment %s.", row.get("id"))
	if removed:
		try:
			staff_queries.mark_synced(supabase, removed)
		except APIError:
			# Not fatal: the nightly job deletes the (already gone) event again and marks it.
			logger.exception("Could not mark %d staff-cancelled appointments as synced.", len(removed))
	return len(cancelled) - len(removed)
