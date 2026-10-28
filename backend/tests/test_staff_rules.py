import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from fastapi import HTTPException
from postgrest.exceptions import APIError
from support import cancelled_row, next_weekday_start, pending_record, staff_user, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.exceptions import AppointmentValidationException, CalendarAccessException
from app.api.v1.appointment.reconcile_replacements import finish_cancelled
from app.api.v1.appointment.slots import get_availability, validate_slot
from app.api.v1.appointment.types import AppointmentPayload, JAKARTA_TZ
from app.api.v1.staff import override
from app.api.v1.staff.types import OverridePayload
from app.google_api.exceptions import GoogleCalendarAccessException, GoogleCalendarOperationException

STAFF = staff_user()
CLOSURE = {"id": "c1", "reason": "AC repair", "start_date": "2030-01-01", "end_date": "2030-01-03"}
EVENTS = "app.api.v1.staff.events."


class OverrideTests(unittest.TestCase):
	def test_override_cancels_the_holder_and_confirms_a_staff_hold(self) -> None:
		start = next_weekday_start(9)
		hold = {**pending_record("hold-id", start), "booker_id": "staff-id"}
		confirmed = {**hold, "status": "confirmed", "sync_status": "synced"}
		payload = OverridePayload(room_number=1, start_time=start, reason="Thesis defence")
		order: list[str] = []

		def slot_taken(*args):
			order.append("database")
			return [cancelled_row(1), {**hold, "id": args[-1]}]

		with (
			patch("app.api.v1.staff.override.staff_queries.override_slot", side_effect=slot_taken),
			patch("app.api.v1.staff.override.room_calendar_id", return_value="cal"),
			patch(EVENTS + "delete_calendar_event") as delete,
			patch(EVENTS + "staff_queries.mark_synced"),
			patch("app.api.v1.staff.override.create_calendar_event", side_effect=lambda *a: order.append("event")) as create,
			patch("app.api.v1.staff.override.appointment_queries.update_own_state") as confirm,
		):
			confirm.side_effect = lambda _s, hold_id, *a: [{**confirmed, "id": hold_id}]
			result = override.override(Mock(), STAFF, payload)
		delete.assert_called_once_with("cal", "ev1")
		self.assertEqual(order, ["event", "database"])  # the calendar is proven writable before anyone is cancelled
		self.assertIn("Reserved by staff: Thesis defence", create.call_args.args[2]["summary"])
		self.assertEqual((result.cancelled, result.appointment.status), (1, "confirmed"))

	def test_a_calendar_that_cannot_be_written_cancels_nobody(self) -> None:
		payload = OverridePayload(room_number=1, start_time=next_weekday_start(9), reason="Thesis defence")
		with (
			patch("app.api.v1.staff.override.room_calendar_id", return_value="cal"),
			patch("app.api.v1.staff.override.create_calendar_event", side_effect=GoogleCalendarAccessException()),
			patch("app.api.v1.staff.override.staff_queries.override_slot") as database,
			self.assertRaises(CalendarAccessException),
		):
			override.override(Mock(), STAFF, payload)
		database.assert_not_called()

	def test_a_database_refusal_removes_the_event_that_was_just_made(self) -> None:
		payload = OverridePayload(room_number=1, start_time=next_weekday_start(9), reason="Thesis defence")
		with (
			patch("app.api.v1.staff.override.room_calendar_id", return_value="cal"),
			patch("app.api.v1.staff.override.create_calendar_event"),
			patch(
				"app.api.v1.staff.override.staff_queries.override_slot",
				side_effect=APIError({"code": "23514", "message": "The room is closed on that date"}),
			),
			patch("app.api.v1.staff.override.delete_calendar_event") as delete,
			self.assertRaises(HTTPException),
		):
			override.override(Mock(), STAFF, payload)
		delete.assert_called_once()


class StaffRulesTests(unittest.TestCase):
	def test_staff_may_take_past_slots_students_may_not(self) -> None:
		past = datetime.combine(date.today() - timedelta(days=30), datetime.min.time(), tzinfo=JAKARTA_TZ).replace(hour=9)
		while past.weekday() > 4:
			past -= timedelta(days=1)
		self.assertEqual(validate_slot(past, 1, staff=True), past)
		with self.assertRaises(AppointmentValidationException):
			validate_slot(past, 1)

	def _availability(self, user, closure=None, used=3):
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[{"booked_starts": [], "bookings_used": used}])
		with patch("app.api.v1.appointment.slots.staff_queries.closure_on", return_value=closure):
			return get_availability(supabase, next_weekday_start(9).date(), 1, user)

	def test_staff_ignore_the_booking_limit_and_a_closure_shuts_the_day(self) -> None:
		self.assertTrue(all(slot.available for slot in self._availability(STAFF).slots))
		self.assertEqual(self._availability(STAFF).bookings_remaining, 3)  # the page shows no limit
		closed = self._availability(STAFF, CLOSURE)
		self.assertFalse(any(slot.available for slot in closed.slots))
		self.assertEqual(closed.closed_reason, "AC repair")

	def test_booking_inside_a_closure_is_refused_before_any_insert(self) -> None:
		supabase = Mock()
		with (
			patch("app.api.v1.appointment.booking.staff_queries.closure_on", return_value=CLOSURE),
			self.assertRaises(AppointmentValidationException) as caught,
		):
			create_appointment(AppointmentPayload(room_number=1, start_time=next_weekday_start(9)), supabase, student_user())
		self.assertIn("AC repair", caught.exception.detail)
		supabase.table.assert_not_called()

	def test_nightly_job_finishes_a_cancelled_booking(self) -> None:
		base = "app.api.v1.appointment.reconcile_replacements."
		with patch(base + "delete_calendar_event") as delete, patch(base + "appointment_queries.update_for_reconciliation") as update:
			self.assertEqual(finish_cancelled(Mock(), cancelled_row(1)), "released")
		delete.assert_called_once_with("cal", "ev1")
		update.assert_called_once_with(ANY, "old1", "cancelled", "synced")
		with patch(base + "delete_calendar_event", side_effect=GoogleCalendarOperationException()), self.assertLogs(base[:-1], level="ERROR"):
			self.assertEqual(finish_cancelled(Mock(), cancelled_row(1)), "failed")


if __name__ == "__main__":
	unittest.main()
