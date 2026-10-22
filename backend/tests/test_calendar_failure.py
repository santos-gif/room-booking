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
				"app.api.v1.appointment.booking.create_calendar_event",
				side_effect=GoogleCalendarOperationException(),
			),
			patch(
				"app.api.v1.appointment.booking.delete_calendar_event",
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
