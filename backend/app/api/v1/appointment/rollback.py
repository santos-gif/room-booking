"""Undo helpers for a booking whose Google Calendar step failed."""
import logging

from postgrest.exceptions import APIError
from supabase import Client

from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)


def mark_failed(supabase: Client, appointment_id: str) -> None:
	"""Keeps the row visible to reconciliation instead of losing track of it."""
	try:
		appointment_queries.update_own_state(supabase, appointment_id, "pending", "failed")
	except APIError:
		logger.exception("Could not mark booking %s as failed.", appointment_id)


def discard_pending_booking(supabase: Client, appointment_id: str) -> None:
	try:
		appointment_queries.discard_own_pending(supabase, appointment_id)
	except APIError:
		logger.exception("Could not discard booking %s.", appointment_id)
		mark_failed(supabase, appointment_id)
