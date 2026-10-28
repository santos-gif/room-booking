"""Closing a room for a range of dates: preview who is affected, close it, list and remove closures."""
from datetime import date, datetime, time, timedelta

from pydantic import TypeAdapter
from supabase import Client

from app.api.v1.appointment.exceptions import AppointmentValidationException
from app.api.v1.appointment.types import JAKARTA_TZ
from app.api.v1.staff.access import staff_db_errors
from app.api.v1.staff.events import remove_events
from app.api.v1.staff.types import ClosurePayload, ClosureResponse, StaffActionResult, StaffBooking
from app.queries import staff as staff_queries


def to_staff_bookings(rows: list[dict[str, object]]) -> list[StaffBooking]:
	return TypeAdapter(list[StaffBooking]).validate_python(rows)


def preview(supabase: Client, room_number: int, start: date, end: date) -> list[StaffBooking]:
	"""The active bookings a closure of these dates would cancel (past bookings are history, not active)."""
	if end < start:
		raise AppointmentValidationException("The end date must be on or after the start date.")
	first = datetime.combine(start, time.min, tzinfo=JAKARTA_TZ)
	after_last = datetime.combine(end + timedelta(days=1), time.min, tzinfo=JAKARTA_TZ)
	with staff_db_errors():
		return to_staff_bookings(staff_queries.list_bookings(supabase, room_number, first, after_last, True))


def create(supabase: Client, payload: ClosurePayload) -> StaffActionResult:
	with staff_db_errors():
		cancelled = staff_queries.create_closure(
			supabase, payload.room_number, payload.start_date, payload.end_date, payload.reason
		)
	return StaffActionResult(cancelled=len(cancelled), events_left=remove_events(supabase, cancelled))


def listing(supabase: Client) -> list[ClosureResponse]:
	return TypeAdapter(list[ClosureResponse]).validate_python(staff_queries.list_closures(supabase))


def remove(supabase: Client, closure_id: str) -> None:
	with staff_db_errors():
		staff_queries.delete_closure(supabase, closure_id)
