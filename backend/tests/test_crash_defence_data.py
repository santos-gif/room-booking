import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Response
from postgrest.exceptions import APIError
from pydantic import ValidationError
from support import next_weekday_start, pending_record, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.reconcile import reconcile_appointments
from app.api.v1.appointment.reconcile_replacements import finish_replacements
from app.api.v1.appointment.types import AppointmentPayload
from app.api.v1.auth.exceptions import CredentialsException, UserNotFoundException
from app.api.v1.auth.helper import get_current_user, save_onboarding
from app.api.v1.auth.types import OnboardingPayload
from app.google_api.exceptions import GoogleCredentialException, GoogleRefreshTokenException


class ReconcileResilienceTests(unittest.TestCase):
	def test_one_bad_row_does_not_stop_the_run(self) -> None:
		rows = [{"id": "bad", "status": "confirmed"}, {"id": "ok", "status": "confirmed"}]
		base = "app.api.v1.appointment.reconcile."
		with (
			patch(base + "appointment_queries.list_for_reconciliation", return_value=rows),
			patch(base + "sync_row", side_effect=[RuntimeError("bad"), "synchronized"]),
			patch(base + "finish_replacements", return_value=(0, 0)),
			self.assertLogs("app.api.v1.appointment.reconcile", level="ERROR"),
		):
			result = reconcile_appointments(Mock())
		self.assertEqual((result.checked, result.synchronized, result.failed), (2, 1, 1))

	def test_one_bad_replacement_does_not_stop_the_rest(self) -> None:
		def pair(n):
			return [
				{"id": f"new{n}", "booker_id": "u", "status": "confirmed", "sync_status": "synced",
					"replaces_appointment_id": f"old{n}"},
				{"id": f"old{n}", "booker_id": "u", "status": "confirmed"},
			]
		base = "app.api.v1.appointment.reconcile_replacements."
		with (
			patch(base + "appointment_queries.update_for_reconciliation", side_effect=[ValueError("x"), None]),
			self.assertLogs("app.api.v1.appointment.reconcile_replacements", level="ERROR"),
		):
			self.assertEqual(finish_replacements(Mock(), pair(1) + pair(2)), (1, 1))


class BookingRollbackTests(unittest.TestCase):
	def test_missing_token_rolls_back_the_pending_row(self) -> None:
		for error in (GoogleRefreshTokenException("none"), GoogleCredentialException("bad")):
			start = next_weekday_start(9)
			supabase = Mock()
			supabase.table.return_value.insert.return_value.execute.return_value = SimpleNamespace(
				data=[pending_record("appointment-id", start)]
			)
			supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
			with (
				patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room"),
				patch("app.api.v1.appointment.booking.create_calendar_event", side_effect=error),
				self.assertRaises(type(error)),
			):
				create_appointment(
					AppointmentPayload(room_number=1, start_time=start),
					supabase, student_user(), None, None, Response(),
				)
			self.assertEqual(supabase.rpc.call_args.args[0], "discard_own_pending_appointment")


class AuthHelperTests(unittest.TestCase):
	def _supabase(self):
		supabase = Mock()
		supabase.auth.get_user.return_value = SimpleNamespace(user=SimpleNamespace(id="a"))
		return supabase

	def test_failed_profile_rpc_is_a_401(self) -> None:
		supabase = self._supabase()
		supabase.rpc.return_value.execute.side_effect = APIError({"code": "PGRST301", "message": "JWT expired"})
		with self.assertRaises(CredentialsException):
			get_current_user(supabase, "token")

	def test_user_row_with_null_email_is_a_404(self) -> None:
		supabase = self._supabase()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data="p")
		supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
			SimpleNamespace(data=[{"id": "p", "email": None}])
		)
		with self.assertRaises(UserNotFoundException):
			get_current_user(supabase, "token")

	def test_duplicate_nim_is_a_409(self) -> None:
		supabase = Mock()
		supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = APIError(
			{"code": "23505", "message": "duplicate key"}
		)
		with self.assertRaises(Exception) as caught:
			save_onboarding(supabase, student_user(), OnboardingPayload(nim=1, major="Management"))
		self.assertEqual(caught.exception.status_code, 409)
		self.assertEqual(caught.exception.detail, "That NIM is already registered.")

	def test_nim_is_capped_below_js_precision_limit(self) -> None:
		self.assertEqual(OnboardingPayload(nim=9_999_999_999_999, major="Management").nim, 9_999_999_999_999)
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=10_000_000_000_000, major="Management")
