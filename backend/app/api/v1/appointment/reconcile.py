"""Cron job that repairs bookings whose Google Calendar event and database row disagree."""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException, Response, status
from postgrest.exceptions import APIError
from supabase import Client

from app.api.v1.appointment.reconcile_replacements import finish_replacements
from app.api.v1.appointment.reconcile_sync import RECONCILE_ERRORS, stored_utc, sync_row
from app.api.v1.appointment.types import ReconciliationResponse
from app.config import settings
from app.google_api.calendar_api import room_calendar_id
from app.google_api.calendar_single_event import delete_calendar_event
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
)
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)
PENDING_GRACE = timedelta(minutes=5)
# Stop early on a slow Google day; the rest is picked up by the next run.
RUN_BUDGET_SECONDS = 45.0


def require_cron_secret(authorization: str | None) -> None:
	if not settings.CRON_SECRET:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Calendar reconciliation is not configured.",
		)
	expected = f"Bearer {settings.CRON_SECRET}".encode()
	# Bytes: compare_digest raises TypeError on a non-ASCII str, which would be a 500.
	if not authorization or not secrets.compare_digest(authorization.encode(), expected):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")


def _discard_stale_pending(supabase: Client, row: dict[str, object]) -> int:
	created = stored_utc(row.get("created_at"))
	# A row without a known age, or a young one, may belong to a request still running.
	if created is None or datetime.now(timezone.utc) - created < PENDING_GRACE:
		return 0
	user_id = row.get("booker_id")
	calendar_id = row.get("google_calendar_id")
	event_id = row.get("google_event_id")
	if isinstance(user_id, str) and isinstance(calendar_id, str) and isinstance(event_id, str):
		# The reply to the original create may have been lost, so the event may exist.
		try:
			delete_calendar_event(supabase, user_id, calendar_id, event_id, None, None, Response())
		except (GoogleAuthorizationException, GoogleRefreshTokenException, GoogleCredentialException):
			# Access was revoked: the event cannot be reached, but the slot must not stay held for ever.
			logger.warning("Could not reach the event of stale appointment %s; releasing the slot.", row.get("id"))
	seconds = int(PENDING_GRACE.total_seconds())
	return 1 if appointment_queries.discard_stale_pending(supabase, row["id"], seconds) else 0


def _reconcile_pending(supabase: Client, row: dict[str, object]) -> str | None:
	"""Never promote a pending booking: its request died, so undo it instead."""
	try:
		return "released" if _discard_stale_pending(supabase, row) else None
	except RECONCILE_ERRORS:
		logger.exception("Pending appointment %s could not be cleaned up.", row.get("id"))
		return "failed"


def _prepare_legacy(supabase: Client, row: dict[str, object]) -> bool:
	"""Give an old row (no Google ids yet) its calendar and event ids. False means it failed."""
	appointment_id = row.get("id")
	room_number = row.get("room_number")
	if not (
		row.get("sync_status") == "legacy"
		and isinstance(appointment_id, str)
		and room_number in (1, 2)
	):
		return True
	try:
		calendar_id = room_calendar_id(room_number)
		event_id = uuid5(NAMESPACE_URL, f"discussion-room-booking:{appointment_id}").hex
		appointment_queries.update_for_reconciliation(
			supabase,
			appointment_id,
			str(row["status"]),
			"pending",
			calendar_id,
			event_id,
			update_google_ids=True,
		)
	except APIError:
		logger.exception(
			"Could not prepare legacy appointment %s for reconciliation.", appointment_id
		)
		return False
	row["google_calendar_id"] = calendar_id
	row["google_event_id"] = event_id
	row["sync_status"] = "pending"
	return True


def _reconcile_row(supabase: Client, row: dict[str, object]) -> str | None:
	if row.get("status") == "pending":
		return _reconcile_pending(supabase, row)
	return sync_row(supabase, row) if _prepare_legacy(supabase, row) else "failed"


def reconcile_appointments(supabase: Client) -> ReconciliationResponse:
	rows = appointment_queries.list_for_reconciliation(supabase)
	counts = {"checked": 0, "synchronized": 0, "released": 0, "failed": 0}
	deadline = time.monotonic() + RUN_BUDGET_SECONDS
	for row in rows:
		if time.monotonic() > deadline:
			logger.warning("Reconciliation budget used up; the remaining rows wait for the next run.")
			break
		if not isinstance(row, dict):
			counts["failed"] += 1
			continue
		counts["checked"] += 1
		try:
			outcome = _reconcile_row(supabase, row)
		except Exception:
			# One bad row must not stop the rest of the cron run.
			logger.exception("Appointment %s crashed during reconciliation.", row.get("id"))
			outcome = "failed"
		if outcome:
			counts[outcome] += 1
	released, failed = finish_replacements(supabase, rows)
	counts["released"] += released
	counts["failed"] += failed
	return ReconciliationResponse(**counts, purged=_purge(supabase))


def _purge(supabase: Client) -> int:
	"""Keeps the database small; a failure here must not fail the repair run."""
	try:
		return appointment_queries.purge_finished(supabase)
	except Exception:
		logger.exception("Garbage collection of finished appointments failed.")
		return 0
