import logging

from supabase import Client

from app.google_api.calendar_single_event import delete_calendar_event
from app.queries import appointments as appointment_queries
from app.queries.appointments import ACTIVE_STATUSES

logger = logging.getLogger(__name__)


def finish_replacements(supabase: Client, rows: list[object]) -> tuple[int, int]:
	"""Cancel the old booking of every confirmed reschedule. Returns (released, failed)."""
	released = 0
	failed = 0
	for replacement in rows:
		if (
			not isinstance(replacement, dict)
			or replacement.get("status") != "confirmed"
			or replacement.get("sync_status") != "synced"
		):
			continue
		old_id = replacement.get("replaces_appointment_id")
		user_id = replacement.get("booker_id")
		if not isinstance(old_id, str) or not isinstance(user_id, str):
			continue
		try:
			old = next(
				(
					row
					for row in rows
					if isinstance(row, dict)
					and row.get("id") == old_id
					and row.get("booker_id") == user_id
					and row.get("status") in ACTIVE_STATUSES
				),
				None,
			)
			if old is None:
				continue
			if isinstance(old.get("google_calendar_id"), str) and isinstance(
				old.get("google_event_id"), str
			):
				delete_calendar_event(old["google_calendar_id"], old["google_event_id"])
			appointment_queries.update_for_reconciliation(supabase, old_id, "cancelled", "synced")
			old["status"] = "cancelled"
			old["sync_status"] = "synced"
			released += 1
		except Exception:
			# Any error (Google, database or a malformed row) counts as failed, not a crash.
			logger.exception("Rescheduled appointment %s could not be finalized.", old_id)
			failed += 1
	return released, failed
