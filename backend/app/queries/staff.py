"""Supabase calls for room closures, staff actions and booking notices. No business rules live here."""
from datetime import date, datetime, timezone

from supabase import Client


def _rows(data: object) -> list[dict[str, object]]:
	return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def closure_on(supabase: Client, room_number: int, day: date) -> dict[str, object] | None:
	"""The closure covering this room on this day, or None."""
	result = (
		supabase.table("room_closures")
		.select("id,reason,start_date,end_date")
		.eq("room_number", room_number)
		.lte("start_date", day.isoformat())
		.gte("end_date", day.isoformat())
		.limit(1)
		.execute()
	)
	rows = _rows(result.data)
	return rows[0] if rows else None


def list_closures(supabase: Client) -> list[dict[str, object]]:
	result = (
		supabase.table("room_closures")
		.select("id,room_number,start_date,end_date,reason")
		.order("start_date", desc=True)
		.limit(100)
		.execute()
	)
	return _rows(result.data)


def list_bookings(
	supabase: Client, room_number: int, start: datetime, end: datetime, future_only: bool
) -> list[dict[str, object]]:
	return _rows(
		supabase.rpc(
			"staff_list_bookings",
			{
				"p_room": room_number,
				"p_from": start.isoformat(),
				"p_to": end.isoformat(),
				"p_future_only": future_only,
			},
		).execute().data
	)


def create_closure(
	supabase: Client, room_number: int, start: date, end: date, reason: str
) -> list[dict[str, object]]:
	"""Records the closure and cancels the active bookings inside it; returns the cancelled rows."""
	return _rows(
		supabase.rpc(
			"staff_create_closure",
			{"p_room": room_number, "p_start": start.isoformat(), "p_end": end.isoformat(), "p_reason": reason},
		).execute().data
	)


def delete_closure(supabase: Client, closure_id: str) -> None:
	supabase.rpc("staff_delete_closure", {"p_id": closure_id}).execute()


def override_slot(
	supabase: Client, room_number: int, start: datetime, reason: str, calendar_id: str, event_id: str, hold_id: str
) -> list[dict[str, object]]:
	"""Cancels whoever holds the slot and inserts the staff booking (pending). Returns every affected row."""
	return _rows(
		supabase.rpc(
			"staff_override_slot",
			{
				"p_room": room_number,
				"p_start": start.isoformat(),
				"p_reason": reason,
				"p_calendar_id": calendar_id,
				"p_event_id": event_id,
				"p_hold_id": hold_id,
			},
		).execute().data
	)


def mark_synced(supabase: Client, appointment_ids: list[str]) -> None:
	supabase.rpc("staff_mark_synced", {"p_ids": appointment_ids}).execute()


def list_notices(supabase: Client) -> list[dict[str, object]]:
	"""The signed-in student's notices they have not dismissed, newest first."""
	result = (
		supabase.table("booking_notices")
		.select("id,message,created_at")
		.is_("seen_at", "null")
		.order("created_at", desc=True)
		.limit(20)
		.execute()
	)
	return _rows(result.data)


def dismiss_notice(supabase: Client, notice_id: str) -> None:
	(
		supabase.table("booking_notices")
		.update({"seen_at": datetime.now(timezone.utc).isoformat()})
		.eq("id", notice_id)
		.execute()
	)
