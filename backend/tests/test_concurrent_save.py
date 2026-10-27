import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from postgrest.exceptions import APIError
from support import next_weekday_start, pending_record, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.exceptions import (
	AppointmentConflictException,
	AppointmentNotFoundException,
	AppointmentStorageException,
	DailyBookingLimitException,
)
from app.api.v1.appointment.types import AppointmentPayload


def db_error(code: str) -> APIError:
	return APIError({"message": "rejected", "code": code, "hint": None, "details": None})


class ConcurrentSaveTests(unittest.TestCase):
	def _book(self, supabase: Mock, create: Mock, user=None) -> None:
		start = next_weekday_start(9)
		with (
			patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room"),
			patch("app.api.v1.appointment.booking_event.create_calendar_event", create),
		):
			create_appointment(
				AppointmentPayload(room_number=1, start_time=start),
				supabase, user or student_user(),
			)

	def _supabase(self, *inserts: object) -> Mock:
		start = next_weekday_start(9)
		supabase = Mock()
		supabase.table.return_value.insert.return_value.execute.side_effect = [
			item if isinstance(item, Exception) else SimpleNamespace(data=[pending_record("a", start)])
			for item in inserts
		]
		confirmed = {**pending_record("a", start), "status": "confirmed", "sync_status": "synced"}
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[confirmed])
		return supabase

	def test_second_student_gets_a_conflict_and_no_second_event(self) -> None:
		supabase = self._supabase("ok", db_error("23P01"))
		create = Mock()
		self._book(supabase, create, student_user("first"))
		with self.assertRaises(AppointmentConflictException) as raised:
			self._book(supabase, create, student_user("second"))
		self.assertEqual(raised.exception.status_code, 409)
		create.assert_called_once()

	def test_fourth_booking_gets_the_limit_message(self) -> None:
		create = Mock()
		with self.assertRaises(DailyBookingLimitException) as raised:
			self._book(self._supabase(db_error("P0001")), create)
		self.assertEqual(raised.exception.detail, "You can have at most three upcoming appointments.")
		create.assert_not_called()

	def test_duplicate_key_is_a_conflict(self) -> None:
		create = Mock()
		with self.assertRaises(AppointmentConflictException):
			self._book(self._supabase(db_error("23505")), create)
		create.assert_not_called()

	def test_unmapped_code_is_a_clean_storage_error_without_an_event(self) -> None:
		create = Mock()
		with self.assertRaises(AppointmentStorageException), self.assertLogs(
			"app.api.v1.appointment.booking", level="ERROR"
		):
			self._book(self._supabase(db_error("XX000")), create)
		create.assert_not_called()

	def test_replacement_of_a_just_cancelled_booking_is_a_404(self) -> None:
		start = next_weekday_start(9)
		create = Mock()
		for code in ("23514", "23503"):
			supabase = self._supabase(db_error(code))
			with (
				patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room"),
				patch("app.api.v1.appointment.booking_event.create_calendar_event", create),
				self.assertRaises(AppointmentNotFoundException),
			):
				create_appointment(
					AppointmentPayload(room_number=1, start_time=start),
					supabase, student_user(), replaces_appointment_id="old",
				)
		create.assert_not_called()
