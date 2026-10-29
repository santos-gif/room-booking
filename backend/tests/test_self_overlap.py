import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from postgrest.exceptions import APIError
from support import next_weekday_start, pending_record, staff_user, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.exceptions import AppointmentValidationException
from app.api.v1.appointment.slots import get_availability
from app.api.v1.appointment.types import AppointmentPayload


def own_booking(start, room=2, booking_id="mine"):
	return {**pending_record(booking_id, start), "room_number": room}


class SelfOverlapTests(unittest.TestCase):
	def _availability(self, user, own, exclude=None):
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[{"booked_starts": [], "bookings_used": 1}])
		start = next_weekday_start(10)
		with (
			patch("app.api.v1.appointment.slots.staff_queries.closure_on", return_value=None),
			patch("app.api.v1.appointment.slots.appointment_queries.list_active", return_value=own(start)),
			patch("app.api.v1.appointment.slots.appointment_queries.get_own", return_value={"id": "mine"}),
		):
			return start, get_availability(supabase, start.date(), 1, user, exclude)

	def test_a_slot_held_in_the_other_room_is_not_offered(self) -> None:
		start, availability = self._availability(student_user(), lambda s: [own_booking(s)])
		by_start = {slot.start_time: slot.available for slot in availability.slots}
		self.assertFalse(by_start[start])
		self.assertTrue(by_start[start.replace(hour=11)])

	def test_the_booking_being_moved_does_not_block_its_own_hour(self) -> None:
		start, availability = self._availability(student_user(), lambda s: [own_booking(s)], exclude="mine")
		self.assertTrue({slot.start_time: slot.available for slot in availability.slots}[start])

	def test_staff_may_hold_both_rooms(self) -> None:
		start, availability = self._availability(staff_user(), lambda s: [own_booking(s)])
		self.assertTrue({slot.start_time: slot.available for slot in availability.slots}[start])

	def test_the_database_refusal_reads_as_a_clear_message(self) -> None:
		start = next_weekday_start(10)
		supabase = Mock()
		supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
			{"code": "23514", "message": "You already hold a room at that time"}
		)
		with (
			patch("app.api.v1.appointment.booking.staff_queries.closure_on", return_value=None),
			patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room"),
			self.assertRaises(AppointmentValidationException) as caught,
		):
			create_appointment(AppointmentPayload(room_number=1, start_time=start), supabase, student_user())
		self.assertEqual(caught.exception.detail, "You already have a room booked at that time.")


if __name__ == "__main__":
	unittest.main()
