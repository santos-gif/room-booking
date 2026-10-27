"""List check: drop bookings whose Google event the owner already deleted."""
import logging
import time
from datetime import datetime, timezone
from typing import TypeGuard

from supabase import Client

from app.api.v1.appointment.calendar_event import booker_name, build_calendar_event
from app.api.v1.appointment.slots import to_responses
from app.api.v1.appointment.types import AppointmentResponse, JAKARTA_TZ
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_single_event import (
	calendar_is_reachable,
	get_calendar_event,
	update_calendar_event,
)
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)

# Each check is up to three Google calls, so only a student's first few (soonest) bookings are looked at;
# a student holds at most three upcoming bookings anyway.
MAX_CHECKED = 10
MAX_TRACKED_USERS = 1000  # cooldown entries kept in memory before the stale ones are swept
# Stop checking after this long so one slow Google day cannot stall the list.
BUDGET_SECONDS = 8.0
COOLDOWN_SECONDS = 30.0
# shortcut: per-instance memory on serverless, so it limits bursts rather than guaranteeing a global limit; use a DB or cache row to make it global
_last_verified: dict[str, float] = {}


def _on_cooldown(user_id: str) -> bool:
	"""True if this user was verified recently; otherwise records the attempt."""
	now = time.monotonic()
	last = _last_verified.get(user_id)
	if last is not None and now - last < COOLDOWN_SECONDS:
		return True
	if len(_last_verified) > MAX_TRACKED_USERS:
		for key in [k for k, v in _last_verified.items() if now - v >= COOLDOWN_SECONDS]:
			del _last_verified[key]
	_last_verified[user_id] = now
	return False


def _check_row(supabase: Client, user: AuthenticatedUser, row: dict[str, object]) -> bool:
	"""False only when Google definitively says the event is gone; raises on any doubt."""
	appointment_id, room = row["id"], row["room_number"]
	event = get_calendar_event(str(row["google_calendar_id"]), str(row["google_event_id"]))
	if event is None and not calendar_is_reachable(str(row["google_calendar_id"])):
		# A 404 can also mean the calendar itself is unknown or no longer shared with the service account.
		logger.warning("Room calendar unreachable; keeping appointment %s.", appointment_id)
		return True
	if event is None or event.get("status") == "cancelled":
		# The same restricted transition a manual cancel uses.
		appointment_queries.update_own_state(supabase, str(appointment_id), "cancelled", "synced")
		try:
			appointment_queries.remove_own_cancelled(supabase, str(appointment_id))
		except Exception:  # noqa: BLE001 - cancelled is enough; the daily purge removes it later
			logger.exception("Could not delete cancelled appointment %s now.", appointment_id)
		return False
	if user.nim is None:
		return True
	start = datetime.fromisoformat(str(row["start_time"])).astimezone(JAKARTA_TZ)
	end = datetime.fromisoformat(str(row["end_time"])).astimezone(JAKARTA_TZ)
	body = build_calendar_event(str(appointment_id), int(str(room)), start, end, booker_name(user), user.nim)
	if event.get("summary") != body["summary"]:
		# Heals events made before the title change; update is a full replace, so send it all.
		update_calendar_event(str(row["google_calendar_id"]), str(row["google_event_id"]), body)
	return True


def _checkable(row: object) -> TypeGuard[dict[str, object]]:
	# Pending rows may be mid-creation (no event yet), so only confirmed ones are judged.
	return (
		isinstance(row, dict)
		and row.get("status") == "confirmed"
		and isinstance(row.get("google_calendar_id"), str)
		and isinstance(row.get("google_event_id"), str)
		and isinstance(row.get("start_time"), str)
		and datetime.fromisoformat(row["start_time"]) > datetime.now(timezone.utc)
	)


def verify_appointments(supabase: Client, user: AuthenticatedUser) -> list[AppointmentResponse]:
	data = appointment_queries.list_active(supabase, user.id)
	if not isinstance(data, list):
		return to_responses(data)
	if _on_cooldown(user.id):
		return to_responses(data)
	deadline = time.monotonic() + BUDGET_SECONDS
	kept: list[object] = []
	checked = 0
	for row in data:
		try:
			if checked < MAX_CHECKED and time.monotonic() < deadline and _checkable(row):
				checked += 1
				if not _check_row(supabase, user, row):
					continue
		except Exception:  # noqa: BLE001 - never drop a booking on uncertainty
			logger.exception("Could not verify appointment %r.", row.get("id") if isinstance(row, dict) else row)
		kept.append(row)
	return to_responses(kept)
