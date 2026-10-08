import unittest
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch, sentinel

from fastapi import HTTPException, Response
from google.auth.exceptions import RefreshError
from pydantic import ValidationError

from app.api.v1.appointment.router import reconcile_calendar
from app.api.v1.appointment.exceptions import (
	AppointmentValidationException,
	CalendarSyncException,
)
from app.api.v1.appointment.helper import (
	_calendar_event,
	_validate_slot,
	create_appointment,
)
from app.api.v1.appointment.types import AppointmentPayload, JAKARTA_TZ
from app.api.v1.auth.exceptions import CredentialsException
from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser, OnboardingPayload
from app.api.v1.google_auth.calendar_helper import (
	_calendar_credentials,
	room_calendar_id,
)
from app.api.v1.google_auth.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
	GoogleConfigurationException,
)
from app.api.v1.google_auth.oauth_flow import create_google_login_response
from app.api.v1.google_auth.oauth_helper import _is_allowed_email
from app.config import (
	settings,
	validate_integration_configuration,
	validate_security_secrets,
)


class BookingContractTests(unittest.IsolatedAsyncioTestCase):
	def test_security_secrets_require_minimum_length_and_separation(self) -> None:
		with (
			patch.object(settings, "SECRET_ACCESS_TOKEN_JWT_KEY", "a" * 32),
			patch.object(settings, "SECRET_REFRESH_TOKEN_JWT_KEY", "b" * 32),
			patch.object(settings, "CRON_SECRET", "c" * 32),
		):
			validate_security_secrets()

		with (
			patch.object(settings, "SECRET_ACCESS_TOKEN_JWT_KEY", "short"),
			patch.object(settings, "SECRET_REFRESH_TOKEN_JWT_KEY", "b" * 32),
			patch.object(settings, "CRON_SECRET", "c" * 32),
			self.assertRaisesRegex(RuntimeError, "SECRET_ACCESS_TOKEN_JWT_KEY"),
		):
			validate_security_secrets()

		with (
			patch.object(settings, "SECRET_ACCESS_TOKEN_JWT_KEY", "a" * 32),
			patch.object(settings, "SECRET_REFRESH_TOKEN_JWT_KEY", "a" * 32),
			patch.object(settings, "CRON_SECRET", "c" * 32),
			self.assertRaisesRegex(RuntimeError, "must be different"),
		):
			validate_security_secrets()

	async def test_reconciliation_requires_configured_bearer_secret(self) -> None:
		secret = "configured-cron-secret-value-12345"
		with (
			patch.object(settings, "CRON_SECRET", secret),
			patch(
				"app.api.v1.appointment.router.reconcile_appointments",
				return_value=sentinel.result,
			) as reconcile,
		):
			result = await reconcile_calendar(object(), f"Bearer {secret}")
			self.assertIs(result, sentinel.result)
			reconcile.assert_called_once()

			with self.assertRaises(HTTPException) as error:
				await reconcile_calendar(object(), "******")
			self.assertEqual(error.exception.status_code, 401)

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
		day = date.today() + timedelta(days=1)
		while day.weekday() > 4:
			day += timedelta(days=1)
		open_slot = datetime.combine(day, time(8), tzinfo=JAKARTA_TZ)
		last_slot = datetime.combine(day, time(16), tzinfo=JAKARTA_TZ)

		self.assertEqual(_validate_slot(open_slot, 1), open_slot)
		self.assertEqual(_validate_slot(last_slot, 2), last_slot)
		with self.assertRaises(AppointmentValidationException):
			_validate_slot(datetime.combine(day, time(17), tzinfo=JAKARTA_TZ), 1)

	def test_onboarding_rejects_unapproved_major_and_nonpositive_nim(self) -> None:
		valid = OnboardingPayload(nim=123456, major="IT")
		self.assertEqual(valid.major, "IT")
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=123456, major="Computer Science")
		with self.assertRaises(ValidationError):
			OnboardingPayload(nim=0, major="IT")

	def test_google_email_domain_validation_is_exact(self) -> None:
		self.assertTrue(_is_allowed_email("student@student.pradita.ac.id"))
		self.assertTrue(_is_allowed_email("staff@pradita.ac.id"))
		self.assertFalse(_is_allowed_email("user@evil-pradita.ac.id"))
		self.assertFalse(_is_allowed_email("user@pradita.ac.id.evil.com"))

	def test_integration_configuration_names_both_room_calendars(self) -> None:
		with (
			patch.object(settings, "SUPABASE_URL", ""),
			patch.object(settings, "SUPABASE_KEY", ""),
			patch.object(settings, "GOOGLE_CLIENT_ID", ""),
			patch.object(settings, "GOOGLE_CLIENT_SECRET", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ID", "legacy-calendar"),
			patch.object(settings, "GOOGLE_TOKEN_ENCRYPTION_KEY", ""),
		):
			with self.assertRaises(RuntimeError) as error:
				validate_integration_configuration()
			message = str(error.exception)
			self.assertIn("GOOGLE_CALENDAR_ROOM_1_ID", message)
			self.assertIn("GOOGLE_CALENDAR_ROOM_2_ID", message)
			self.assertIn("GOOGLE_CALENDAR_ID is not used", message)

	def test_integration_configuration_rejects_invalid_fernet_key(self) -> None:
		with (
			patch.object(settings, "SUPABASE_URL", "https://example.supabase.co"),
			patch.object(settings, "SUPABASE_KEY", "test-key"),
			patch.object(settings, "GOOGLE_CLIENT_ID", "test-client-id"),
			patch.object(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
			patch.object(settings, "GOOGLE_REDIRECT_URI", "http://localhost/callback"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", "room-1"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", "room-2"),
			patch.object(settings, "GOOGLE_TOKEN_ENCRYPTION_KEY", "invalid"),
		):
			with self.assertRaisesRegex(RuntimeError, "valid Fernet key"):
				validate_integration_configuration()

	def test_google_login_requests_calendar_events_and_configured_callback(self) -> None:
		redirect_uri = "https://api.example.test/api/v1/google-auth/oauth2callback"
		with (
			patch.object(settings, "GOOGLE_CLIENT_ID", "test-client-id"),
			patch.object(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
			patch.object(settings, "GOOGLE_REDIRECT_URI", redirect_uri),
			patch.object(settings, "COOKIE_SECURE", False),
		):
			response = create_google_login_response()

		query = parse_qs(urlparse(response.headers["location"]).query)
		self.assertEqual(query["redirect_uri"], [redirect_uri])
		self.assertEqual(query["access_type"], ["offline"])
		self.assertIn("consent", query["prompt"][0])
		self.assertIn(
			"https://www.googleapis.com/auth/calendar.events",
			query["scope"][0].split(),
		)
		self.assertTrue(query["state"][0])
		self.assertIn(
			f"google_oauth_state={query['state'][0]}",
			response.headers["set-cookie"],
		)

	def test_calendar_event_serializes_jakarta_wall_time_and_zone(self) -> None:
		start = datetime(2026, 10, 9, 19, 0, tzinfo=JAKARTA_TZ)
		event = _calendar_event(
			"appointment-test-id",
			1,
			start,
			start + timedelta(hours=1),
		)

		self.assertEqual(event["start"]["dateTime"], "2026-10-09T19:00:00+07:00")
		self.assertEqual(event["start"]["timeZone"], "Asia/Jakarta")
		self.assertEqual(event["end"]["dateTime"], "2026-10-09T20:00:00+07:00")

	def test_selected_room_uses_its_configured_calendar(self) -> None:
		with (
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", "room-one"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", "room-two"),
		):
			self.assertEqual(room_calendar_id(1), "room-one")
			self.assertEqual(room_calendar_id(2), "room-two")

			with self.assertRaises(GoogleConfigurationException):
				room_calendar_id(3)

	def test_revoked_google_refresh_token_is_invalidated(self) -> None:
		supabase = Mock()
		supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
			SimpleNamespace(
				data=[{"refresh_token": "encrypted-token", "is_valid": True}]
			)
		)
		with (
			patch(
				"app.api.v1.google_auth.calendar_helper.decrypt_refresh_token",
				return_value="refresh-token",
			),
			patch(
				"app.api.v1.google_auth.calendar_helper.Credentials.refresh",
				side_effect=RefreshError("invalid_grant"),
			),
			self.assertRaises(GoogleAuthorizationException),
		):
			_calendar_credentials(
				supabase,
				"user-id",
				None,
				None,
				Response(),
			)

		supabase.table.return_value.update.assert_called_once_with({"is_valid": False})
		supabase.table.return_value.update.return_value.eq.assert_called_once_with(
			"id",
			"user-id",
		)

	def test_appointment_persists_and_syncs_calendar_event(self) -> None:
		booking_day = date.today() + timedelta(days=1)
		while booking_day.weekday() > 4:
			booking_day += timedelta(days=1)
		start = datetime.combine(booking_day, time(9), tzinfo=JAKARTA_TZ)
		appointment_id = "8d4f7ca5-6181-4a42-97d4-641827741219"
		event_uuid = "5b3f4a2d9ea748b190d119a67d256a36"
		inserted_record = {
			"id": appointment_id,
			"booker_id": "user-id",
			"room_number": 1,
			"start_time": start.astimezone(timezone.utc).isoformat(),
			"end_time": (start + timedelta(hours=1))
			.astimezone(timezone.utc)
			.isoformat(),
			"status": "pending",
			"sync_status": "pending",
		}
		confirmed_record = {
			**inserted_record,
			"status": "confirmed",
			"sync_status": "synced",
		}
		supabase = Mock()
		table = supabase.table.return_value
		table.insert.return_value.execute.return_value = SimpleNamespace(
			data=[inserted_record]
		)
		table.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(
			data=[confirmed_record]
		)
		user = AuthenticatedUser(id="user-id", email="student@student.pradita.ac.id")
		payload = AppointmentPayload(room_number=1, start_time=start)
		response = Response()
		with (
			patch("app.api.v1.appointment.helper.uuid4", side_effect=[
				appointment_id,
				SimpleNamespace(hex=event_uuid),
			]),
			patch(
				"app.api.v1.appointment.helper.room_calendar_id",
				return_value="room-calendar",
			),
			patch(
				"app.api.v1.appointment.helper.create_calendar_event",
				return_value={"id": event_uuid},
			) as create_event,
		):
			result = create_appointment(
				payload,
				supabase,
				user,
				"access-token",
				None,
				response,
			)

		self.assertEqual(result.status, "confirmed")
		self.assertEqual(result.sync_status, "synced")
		inserted_values = table.insert.call_args.args[0]
		self.assertEqual(inserted_values["booker_id"], "user-id")
		self.assertEqual(inserted_values["room_number"], 1)
		self.assertEqual(
			datetime.fromisoformat(inserted_values["start_time"]).astimezone(
				JAKARTA_TZ
			),
			start,
		)
		event_body = create_event.call_args.args[4]
		self.assertEqual(event_body["start"]["timeZone"], "Asia/Jakarta")
		self.assertEqual(event_body["start"]["dateTime"], start.isoformat())
		self.assertEqual(
			event_body["end"]["dateTime"],
			(start + timedelta(hours=1)).isoformat(),
		)

	def test_calendar_failure_does_not_confirm_appointment(self) -> None:
		booking_day = date.today() + timedelta(days=1)
		while booking_day.weekday() > 4:
			booking_day += timedelta(days=1)
		start = datetime.combine(booking_day, time(9), tzinfo=JAKARTA_TZ)
		pending_record = {
			"id": "appointment-id",
			"booker_id": "user-id",
			"room_number": 1,
			"start_time": start.astimezone(timezone.utc).isoformat(),
			"end_time": (start + timedelta(hours=1))
			.astimezone(timezone.utc)
			.isoformat(),
			"status": "pending",
			"sync_status": "pending",
		}
		supabase = Mock()
		table = supabase.table.return_value
		table.insert.return_value.execute.return_value = SimpleNamespace(
			data=[pending_record]
		)
		table.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(
			data=[{**pending_record, "sync_status": "failed"}]
		)
		user = AuthenticatedUser(id="user-id", email="student@student.pradita.ac.id")
		with (
			patch("app.api.v1.appointment.helper.uuid4", side_effect=[
				"appointment-id",
				SimpleNamespace(hex="event-id"),
			]),
			patch(
				"app.api.v1.appointment.helper.room_calendar_id",
				return_value="room-calendar",
			),
			patch(
				"app.api.v1.appointment.helper.create_calendar_event",
				side_effect=GoogleCalendarOperationException(),
			),
			self.assertRaises(CalendarSyncException),
			self.assertLogs(
				"app.api.v1.appointment.helper",
				level="ERROR",
			),
		):
			create_appointment(
				AppointmentPayload(room_number=1, start_time=start),
				supabase,
				user,
				None,
				None,
				Response(),
			)

		table.update.assert_called_once_with({"sync_status": "failed"})

	def test_booking_requires_an_authenticated_user(self) -> None:
		with self.assertRaises(CredentialsException):
			get_current_user(Mock(), None)


if __name__ == "__main__":
	unittest.main()
