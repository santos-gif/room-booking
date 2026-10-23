"""Supabase table and RPC calls for appointments. No business rules live here."""
from datetime import date, datetime, timezone

from postgrest.types import JSON
from supabase import Client

from app.config import settings

ACTIVE_STATUSES = ("pending", "confirmed")


def list_active(supabase: Client, user_id: str) -> object:
	"""The user's upcoming pending/confirmed bookings, soonest first."""
	return (
		supabase.table("appointments")
		.select("*")
		.eq("booker_id", user_id)
		.in_("status", list(ACTIVE_STATUSES))
		.gte("start_time", datetime.now(timezone.utc).isoformat())
		.order("start_time")
		.execute()
		.data
	)


def get_own(supabase: Client, appointment_id: str, user_id: str) -> dict[str, object] | None:
	result = (
		supabase.table("appointments")
		.select("*")
		.eq("id", appointment_id)
		.eq("booker_id", user_id)
		.in_("status", list(ACTIVE_STATUSES))
		.limit(1)
		.execute()
	)
	if not result.data or not isinstance(result.data[0], dict):
		return None
	return result.data[0]


def insert(supabase: Client, values: JSON) -> object:
	return supabase.table("appointments").insert(values).execute().data


def update_own_state(
	supabase: Client,
	appointment_id: str,
	status: str,
	sync_status: str,
) -> object:
	return supabase.rpc(
		"update_own_appointment_state",
		{
			"target_appointment_id": appointment_id,
			"new_status": status,
			"new_sync_status": sync_status,
		},
	).execute().data


def remove_own_cancelled(supabase: Client, appointment_id: str) -> bool:
	"""Deletes the caller's own cancelled booking; False if it is still referenced or not theirs."""
	data = supabase.rpc(
		"remove_own_cancelled_appointment", {"target_appointment_id": appointment_id}
	).execute().data
	return bool(data)


def purge_finished(supabase: Client) -> int:
	"""Garbage collection: deletes cancelled and already-ended bookings, returns how many."""
	data = supabase.rpc(
		"purge_finished_appointments", {"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET}
	).execute().data
	return data if isinstance(data, int) else 0


def discard_own_pending(supabase: Client, appointment_id: str) -> None:
	supabase.rpc(
		"discard_own_pending_appointment",
		{"target_appointment_id": appointment_id},
	).execute()


def availability(
	supabase: Client,
	booking_date: date,
	room_number: int,
	exclude_appointment_id: str | None,
) -> object:
	return (
		supabase.rpc(
			"get_booking_availability",
			{
				"booking_date": booking_date.isoformat(),
				"requested_room": room_number,
				"excluded_appointment_id": exclude_appointment_id,
			},
		)
		.execute()
		.data
	)


def list_for_reconciliation(supabase: Client) -> list[object]:
	return supabase.rpc(
		"list_reconciliation_appointments",
		{"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET},
	).execute().data


def update_for_reconciliation(
	supabase: Client,
	appointment_id: str,
	status: str,
	sync_status: str,
	calendar_id: str | None = None,
	event_id: str | None = None,
	update_google_ids: bool = False,
) -> None:
	supabase.rpc(
		"update_reconciliation_appointment",
		{
			"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET,
			"appointment_id": appointment_id,
			"new_status": status,
			"new_sync_status": sync_status,
			"new_calendar_id": calendar_id,
			"new_event_id": event_id,
			"update_google_ids": update_google_ids,
		},
	).execute()


def discard_stale_pending(supabase: Client, appointment_id: object, min_age_seconds: int) -> bool:
	"""True when the database actually removed the row."""
	result = supabase.rpc(
		"discard_stale_pending_appointment",
		{
			"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET,
			"appointment_id": appointment_id,
			"min_age_seconds": min_age_seconds,
		},
	).execute()
	return bool(result.data)
