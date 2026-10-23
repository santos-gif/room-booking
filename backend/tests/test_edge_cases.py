import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from support import student_user

from app.api.v1.appointment.slots import MAX_ADVANCE, get_availability
from app.api.v1.appointment.types import JAKARTA_TZ
from app.queries import appointments as queries


class RunningBookingTests(unittest.TestCase):
	def test_list_keeps_a_booking_that_started_but_has_not_ended(self) -> None:
		supabase = Mock()
		chain = supabase.table.return_value.select.return_value.eq.return_value.in_.return_value
		chain.gt.return_value.order.return_value.execute.return_value = SimpleNamespace(data=[])
		queries.list_active(supabase, "user-id")
		column, _ = chain.gt.call_args.args
		self.assertEqual(column, "end_time")  # not start_time: the limit counts a running booking too
		chain.gte.assert_not_called()


class FarFutureAvailabilityTests(unittest.TestCase):
	def test_slots_past_the_booking_window_are_not_offered(self) -> None:
		last_day = datetime.now(JAKARTA_TZ).date() + MAX_ADVANCE
		while last_day.weekday() > 4:
			last_day -= timedelta(days=1)
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{"booked_starts": [], "bookings_used": 0}]
		)
		slots = get_availability(supabase, last_day, 1, student_user()).slots
		limit = datetime.now(JAKARTA_TZ) + MAX_ADVANCE
		for slot in slots:  # exactly what booking accepts: the same bound validate_slot uses
			self.assertEqual(slot.available, slot.start_time <= limit)
