import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.v1.appointment.exceptions import (
	AppointmentStorageException,
	AppointmentValidationException,
)
from app.api.v1.appointment.slots import LEAD, validate_slot, get_availability
from app.api.v1.appointment.types import JAKARTA_TZ

from support import student_user

SLOT = datetime(2030, 1, 2, 16, 0, tzinfo=JAKARTA_TZ)  # a Wednesday


def clock(hour: int, minute: int, second: int):
	"""Patch slots.datetime so now() is the given time on the slot's day."""
	fixed = datetime(2030, 1, 2, hour, minute, second, tzinfo=JAKARTA_TZ)

	class FakeDatetime(datetime):
		@classmethod
		def now(cls, tz=None):
			return fixed

	return patch("app.api.v1.appointment.slots.datetime", FakeDatetime)


class LeadRuleTests(unittest.TestCase):
	def test_lead_is_five_minutes(self) -> None:
		self.assertEqual(LEAD.total_seconds(), 300)

	def test_validation_closes_five_minutes_before_start(self) -> None:
		with clock(15, 54, 59):
			self.assertEqual(validate_slot(SLOT, 1), SLOT)
		for second in (0, 1):
			with clock(15, 55, second), self.assertRaises(AppointmentValidationException) as caught:
				validate_slot(SLOT, 1)
			self.assertIn("5 minutes", caught.exception.detail)

	def _slot_16(self):
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{"booked_starts": [], "bookings_used": 0}]
		)
		slots = get_availability(supabase, date(2030, 1, 2), 1, student_user()).slots
		return next(slot for slot in slots if slot.start_time == SLOT)

	def test_availability_closes_five_minutes_before_start(self) -> None:
		with clock(15, 54, 59):
			self.assertTrue(self._slot_16().available)
		for second in (0, 1):
			with clock(15, 55, second):
				self.assertFalse(self._slot_16().available)

	def test_bad_stored_booked_start_is_a_storage_error(self) -> None:
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{"booked_starts": ["not-a-date"], "bookings_used": 0}]
		)
		with self.assertRaises(AppointmentStorageException):
			get_availability(supabase, date(2030, 1, 2), 1, student_user())
