import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from app.api.v1.appointment.slots import get_availability

from support import next_weekday_start, student_user


class AvailabilityTests(unittest.TestCase):
	def test_availability_uses_aggregate_rpc_without_returning_other_bookings(self) -> None:
		booked_start = next_weekday_start(9)  # inside the 90-day window, or slots are not offered at all
		booking_date = booked_start.date()
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[
				{
					"booked_starts": [booked_start.isoformat()],
					"bookings_used": 1,
				}
			]
		)

		availability = get_availability(supabase, booking_date, 1, student_user("profile-id"))

		self.assertEqual(availability.bookings_used, 1)
		self.assertEqual(availability.bookings_remaining, 2)
		self.assertFalse(availability.slots[1].available)
		self.assertTrue(availability.slots[2].available)

	def test_availability_closes_every_slot_at_the_booking_limit(self) -> None:
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{"booked_starts": [], "bookings_used": 3}]
		)

		availability = get_availability(supabase, date(2030, 1, 1), 1, student_user("profile-id"))

		self.assertEqual(availability.bookings_remaining, 0)
		self.assertFalse(any(slot.available for slot in availability.slots))
		supabase.rpc.assert_called_once_with(
			"get_booking_availability",
			{
				"booking_date": "2030-01-01",
				"requested_room": 1,
				"excluded_appointment_id": None,
			},
		)
		supabase.table.assert_called_once_with("room_closures")  # the only table read: closures
