"""List check: drop bookings whose Google event the owner already deleted."""
import logging
import time
from datetime import datetime, timezone

from fastapi import Response
from supabase import Client

from app.api.v1.appointment.slots import _booker_name, _calendar_event, _responses
from app.api.v1.appointment.types import AppointmentResponse, JAKARTA_TZ
from app.api.v1.auth.types import AuthenticatedUser
from app.google_api.calendar_single_event import (
	calendar_is_reachable,
	get_calendar_event,
	update_calendar_event,
)
from app.queries import appointments as appointment_queries

logger = logging.getLogger(__name__)

MAX_CHECKED = 10
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
	if len(_last_verified) > 1000:
		for key in [k for k, v in _last_verified.items() if now - v >= COOLDOWN_SECONDS]:
			del _last_verified[key]
	_last_verified[user_id] = now
	return False


def _check_row(supabase: Client, user: AuthenticatedUser, row: dict[str, object]) -> bool:
	"""False only when Google definitively says the event is gone; raises on any doubt."""
	appointment_id, room = row["id"], row["room_number"]
	event = get_calendar_event(
		supabase, user.id, str(row["google_calendar_id"]), str(row["google_event_id"]),
		None, None, Response(),
	)
	if event is None and not calendar_is_reachable(supabase, user.id, str(row["google_calendar_id"])):
		# A 404 can also mean the calendar itself is unknown or no longer shared with this user.
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
	body = _calendar_event(str(appointment_id), int(str(room)), start, end, _booker_name(user), user.nim)
	if event.get("summary") != body["summary"]:
		# Heals events made before the title change; update is a full replace, so send it all.
		update_calendar_event(
			supabase, user.id, str(row["google_calendar_id"]), str(row["google_event_id"]),
			body, None, None, Response(),
		)
	return True


def _checkable(row: object) -> bool:
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
		return _responses(data)
	if _on_cooldown(user.id):
		return _responses(data)
	deadline = time.monotonic() + BUDGET_SECONDS
	kept: list[object] = []
	checked = 0
	for row in data:
		try:
			if checked < MAX_CHECKED and time.monotonic() < deadline and _checkable(row):
				checked += 1
				if not _check_row(supabase, user, row):  # type: ignore[arg-type]
					continue
		except Exception:  # noqa: BLE001 - never drop a booking on uncertainty
			logger.exception("Could not verify appointment %r.", row.get("id") if isinstance(row, dict) else row)
		kept.append(row)
	return _responses(kept)
