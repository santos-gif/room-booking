import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Response
from support import next_weekday_start, pending_record, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.exceptions import CalendarSyncException
from app.api.v1.appointment.types import AppointmentPayload
from app.google_api.exceptions import GoogleCalendarOperationException


class AppointmentFlowTests(unittest.TestCase):
	def _book_with_calendar_failure(self, delete_effect: object = None) -> Mock:
		start = next_weekday_start(9)
		supabase = Mock()
		table = supabase.table.return_value
		table.insert.return_value.execute.return_value = SimpleNamespace(
			data=[pending_record("appointment-id", start)]
		)
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
		with (
			patch("app.api.v1.appointment.booking.uuid4", side_effect=[
				"appointment-id",
				SimpleNamespace(hex="event-id"),
			]),
			patch(
				"app.api.v1.appointment.booking.room_calendar_id",
				return_value="room-calendar",
			),
			patch(
				"app.api.v1.appointment.booking_event.create_calendar_event",
				side_effect=GoogleCalendarOperationException(),
			),
			patch(
				"app.api.v1.appointment.booking_event.delete_calendar_event",
				side_effect=delete_effect,
			),
			self.assertRaises(CalendarSyncException),
			self.assertLogs(
				"app.api.v1.appointment.booking",
				level="ERROR",
			),
		):
			create_appointment(
				AppointmentPayload(room_number=1, start_time=start),
				supabase,
				student_user(),
				None,
				None,
				Response(),
			)

		return supabase

	def test_calendar_failure_removes_the_booking(self) -> None:
		supabase = self._book_with_calendar_failure()

		supabase.rpc.assert_called_once_with(
			"discard_own_pending_appointment",
			{"target_appointment_id": "appointment-id"},
		)

	def test_failed_event_cleanup_keeps_booking_for_reconciliation(self) -> None:
		supabase = self._book_with_calendar_failure(GoogleCalendarOperationException())

		supabase.rpc.assert_called_once_with(
			"update_own_appointment_state",
			{
				"target_appointment_id": "appointment-id",
				"new_status": "pending",
				"new_sync_status": "failed",
			},
		)


class CalendarAccessTests(unittest.TestCase):
	"""A student whose Google account cannot write to the room calendar gets an actionable message."""

	def _book(self, effect: Exception):
		from fastapi import Response as FastResponse

		start = next_weekday_start(9)
		supabase = Mock()
		supabase.table.return_value.insert.return_value.execute.return_value = SimpleNamespace(
			data=[pending_record("appointment-id", start)]
		)
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
		with (
			patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room-calendar"),
			patch("app.api.v1.appointment.booking_event.create_calendar_event", side_effect=effect),
			patch("app.api.v1.appointment.booking_event.delete_calendar_event"),
			self.assertLogs("app.api.v1.appointment.booking", level="ERROR"),
		):
			create_appointment(
				AppointmentPayload(room_number=1, start_time=start), supabase, student_user(), None, None, FastResponse()
			)

	def test_no_write_access_says_to_ask_for_the_calendar_to_be_shared(self) -> None:
		from app.api.v1.appointment.exceptions import CalendarAccessException
		from app.google_api.exceptions import GoogleCalendarAccessException

		with self.assertRaises(CalendarAccessException) as caught:
			self._book(GoogleCalendarAccessException())
		self.assertEqual(caught.exception.status_code, 403)
		self.assertIn("share the calendar", caught.exception.detail)

	def test_other_calendar_failures_keep_the_generic_message(self) -> None:
		with self.assertRaises(CalendarSyncException):
			self._book(GoogleCalendarOperationException())

	def test_403_and_404_from_google_mean_no_access_but_a_rate_limit_does_not(self) -> None:
		from googleapiclient.errors import HttpError

		from app.google_api.calendar_api import _no_write_access

		def err(status: int, body: bytes = b"{}") -> HttpError:
			return HttpError(SimpleNamespace(status=status, reason="x"), body)

		self.assertTrue(_no_write_access(err(404)))
		self.assertTrue(_no_write_access(err(403, b'{"error":{"errors":[{"reason":"forbidden"}]}}')))
		self.assertFalse(_no_write_access(err(403, b'{"error":{"errors":[{"reason":"rateLimitExceeded"}]}}')))
		self.assertFalse(_no_write_access(err(500)))
