import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from googleapiclient.errors import HttpError
from support import next_weekday_start, student_user

from app.api.v1.appointment.cancel import cancel_appointment
from app.api.v1.appointment.exceptions import AppointmentNotFoundException
from app.api.v1.appointment.reschedule import reschedule_appointment
from app.api.v1.appointment.types import ReschedulePayload
from app.google_api.calendar_single_event import delete_calendar_event

SERVICE = "app.google_api.calendar_single_event.calendar_service"


def gone(status: int) -> Mock:
	"""A Google service whose delete answers like an already-removed event."""
	service = Mock()
	service.events.return_value.delete.return_value.execute.side_effect = HttpError(
		SimpleNamespace(status=status, reason="Gone"), b""
	)
	return service


def supabase_with(rows: list[dict[str, object]]) -> Mock:
	supabase = Mock()
	(
		supabase.table.return_value.select.return_value.eq.return_value.eq.return_value
		.in_.return_value.limit.return_value.execute.return_value
	) = SimpleNamespace(data=rows)
	supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[{"id": "old"}])
	return supabase


def old_row() -> dict[str, object]:
	start = next_weekday_start(9)
	return {
		"id": "old", "booker_id": "user-id", "room_number": 1, "start_time": start.isoformat(),
		"google_calendar_id": "cal", "google_event_id": "ev",
	}


class GoneEventTests(unittest.TestCase):
	def test_delete_treats_404_and_410_as_success(self) -> None:
		for status in (404, 410):
			with patch(SERVICE, return_value=gone(status)):
				delete_calendar_event("cal", "ev")

	def test_cancel_succeeds_when_the_event_is_already_gone(self) -> None:
		supabase = supabase_with([old_row()])
		with patch(SERVICE, return_value=gone(404)):
			cancel_appointment("old", supabase, student_user())
		calls = {c.args[0]: c.args[1] for c in supabase.rpc.call_args_list}
		self.assertEqual(calls["update_own_appointment_state"]["new_status"], "cancelled")
		# ...and the cancelled row is deleted right away, so it never lingers in the database.
		self.assertEqual(calls["remove_own_cancelled_appointment"], {"target_appointment_id": "old"})

	def test_reschedule_succeeds_when_the_old_event_is_already_gone(self) -> None:
		supabase = supabase_with([old_row()])
		new = SimpleNamespace(id="new")
		payload = ReschedulePayload(room_number=2, start_time=next_weekday_start(11))
		with (
			patch(SERVICE, return_value=gone(410)),
			patch("app.api.v1.appointment.reschedule.create_appointment", return_value=new),
		):
			result = reschedule_appointment("old", payload, supabase, student_user())
		self.assertIs(result, new)
		self.assertEqual(supabase.rpc.call_args.args[1]["target_appointment_id"], "old")

	def test_reschedule_of_a_missing_or_cancelled_booking_is_a_404(self) -> None:
		payload = ReschedulePayload(room_number=2, start_time=next_weekday_start(11))
		with patch("app.api.v1.appointment.reschedule.create_appointment") as create:
			with self.assertRaises(AppointmentNotFoundException) as raised:
				reschedule_appointment("old", payload, supabase_with([]), student_user())
		self.assertEqual(raised.exception.status_code, 404)
		create.assert_not_called()


class CancelCleanupTests(unittest.TestCase):
	def test_cancel_still_succeeds_when_the_immediate_delete_fails(self) -> None:
		supabase = supabase_with([old_row()])
		with (
			patch(SERVICE, return_value=gone(404)),
			patch("app.api.v1.appointment.cancel.appointment_queries.remove_own_cancelled", side_effect=RuntimeError("db")),
			self.assertLogs("app.api.v1.appointment.cancel", level="ERROR"),
		):
			cancel_appointment("old", supabase, student_user())
