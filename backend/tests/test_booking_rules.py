import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.api.v1.appointment.exceptions import AppointmentValidationException
from app.api.v1.appointment.slots import _validate_slot
from app.api.v1.appointment.types import AppointmentPayload, JAKARTA_TZ
from app.api.v1.auth.types import OnboardingPayload

from support import next_weekday_start


class BookingRuleTests(unittest.TestCase):
	def test_jakarta_timestamp_round_trips_to_utc(self) -> None:
		payload = AppointmentPayload.model_validate(
			{
				"room_number": 1,
				"start_time": "2026-10-06T19:00:00+07:00",
			}
		)
		self.assertEqual(
			payload.start_time.astimezone(timezone.utc).isoformat(),
			"2026-10-06T12:00:00+00:00",
		)

	def test_booking_request_does_not_accept_client_ownership_or_end_time(self) -> None:
		with self.assertRaises(ValidationError):
			AppointmentPayload.model_validate(
				{
					"room_number": 1,
					"start_time": "2026-10-06T19:00:00+07:00",
					"booker_id": "client-controlled",
					"end_time": "2026-10-06T20:00:00+07:00",
				}
			)

	def test_naive_booking_time_is_interpreted_as_jakarta(self) -> None:
		payload = AppointmentPayload(
			room_number=1,
			start_time=datetime(2026, 10, 6, 19, 0),
		)

		self.assertEqual(payload.start_time.tzinfo, JAKARTA_TZ)
		self.assertEqual(
			payload.start_time.astimezone(timezone.utc).hour,
			12,
		)

	def test_only_future_weekday_booking_hours_are_allowed(self) -> None:
		open_slot = next_weekday_start(8)
		last_slot = next_weekday_start(16)

		self.assertEqual(_validate_slot(open_slot, 1), open_slot)
		self.assertEqual(_validate_slot(last_slot, 2), last_slot)
		with self.assertRaises(AppointmentValidationException):
			_validate_slot(next_weekday_start(17), 1)

	def test_onboarding_rejects_unapproved_major_and_nonpositive_nim(self) -> None:
		valid = OnboardingPayload(nim=123456, major="Information Technology")
		self.assertEqual(valid.major, "Information Technology")
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=123456, major="Computer Science")
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=0, major="Information Technology")
		# A real 10-digit NIM is above the old 32-bit limit and must be accepted.
		self.assertEqual(OnboardingPayload(nim=2_510_101_051, major="Information Technology").nim, 2_510_101_051)
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=9_223_372_036_854_775_808, major="Information Technology")
