import unittest
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch, sentinel

from fastapi import HTTPException, Response
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from postgrest.exceptions import APIError
from pydantic import ValidationError
from starlette.requests import Request

from app.api.v1.appointment.router import reconcile_calendar
from app.api.v1.appointment.exceptions import (
	AppointmentValidationException,
	CalendarSyncException,
)
from app.api.v1.appointment.helper import (
	_calendar_event,
	_validate_slot,
	cancel_appointment,
	create_appointment,
	get_availability,
)
from app.api.v1.appointment.types import AppointmentPayload, JAKARTA_TZ
from app.api.v1.auth.exceptions import CredentialsException
from app.api.v1.auth.helper import get_current_user, renew_tokens
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
from app.api.v1.google_auth.oauth_helper import (
	_is_allowed_email,
	complete_google_oauth,
)
from app.config import (
	settings,
	validate_integration_configuration,
	validate_security_secrets,
)
from app.database import create_supabase_client


class BookingContractTests(unittest.IsolatedAsyncioTestCase):
	def test_security_secrets_require_minimum_length_and_separation(self) -> None:
		with (
			patch.object(settings, "CRON_SECRET", "c" * 32),
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "d" * 32),
		):
			validate_security_secrets()

		with (
			patch.object(settings, "CRON_SECRET", "short"),
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "d" * 32),
			self.assertRaisesRegex(RuntimeError, "CRON_SECRET"),
		):
			validate_security_secrets()

		with (
			patch.object(settings, "CRON_SECRET", "c" * 32),
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "c" * 32),
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
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "rpc-secret"),
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
		supabase.rpc.return_value.execute.return_value = (
			SimpleNamespace(
				data=[{"refresh_token": "encrypted-token", "is_valid": True}]
			)
		)
		with (
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "backend-rpc-secret"),
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

		supabase.rpc.assert_any_call(
			"invalidate_google_refresh_token",
			{
				"requested_profile_id": "user-id",
				"backend_secret": "backend-rpc-secret",
			},
		)

	def test_cancellation_uses_the_restricted_state_transition_rpc(self) -> None:
		appointment = {
			"id": "appointment-id",
			"booker_id": "user-id",
			"status": "confirmed",
		}
		supabase = Mock()
		(
			supabase.table.return_value.select.return_value
			.eq.return_value.eq.return_value.in_.return_value
			.limit.return_value.execute.return_value
		) = SimpleNamespace(data=[appointment])
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{**appointment, "status": "cancelled", "sync_status": "synced"}]
		)
		user = AuthenticatedUser(id="user-id", email="student@student.pradita.ac.id")

		cancel_appointment(
			"appointment-id",
			supabase,
			user,
			None,
			None,
			Response(),
		)

		supabase.rpc.assert_called_once_with(
			"update_own_appointment_state",
			{
				"target_appointment_id": "appointment-id",
				"new_status": "cancelled",
				"new_sync_status": "synced",
			},
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
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
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
		supabase.rpc.assert_called_once_with(
			"update_own_appointment_state",
			{
				"target_appointment_id": appointment_id,
				"new_status": "confirmed",
				"new_sync_status": "synced",
			},
		)
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
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[])
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

		supabase.rpc.assert_called_once_with(
			"update_own_appointment_state",
			{
				"target_appointment_id": "appointment-id",
				"new_status": "pending",
				"new_sync_status": "failed",
			},
		)

	def test_booking_requires_an_authenticated_user(self) -> None:
		with self.assertRaises(CredentialsException):
			get_current_user(Mock(), None)

	def test_authenticated_user_is_resolved_through_auth_profile_mapping(self) -> None:
		supabase = Mock()
		supabase.auth.get_user.return_value = SimpleNamespace(
			user=SimpleNamespace(id="auth-user-id")
		)
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data="legacy-profile-id"
		)
		supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
			SimpleNamespace(
				data=[
					{
						"id": "legacy-profile-id",
						"email": "student@student.pradita.ac.id",
						"name": "Student",
						"nim": 123456,
						"major": "IT",
					}
				]
			)
		)

		user = get_current_user(supabase, "supabase-access-token")

		self.assertEqual(user.id, "legacy-profile-id")
		supabase.auth.get_user.assert_called_once_with("supabase-access-token")
		supabase.rpc.assert_called_once_with("current_profile_id")
		supabase.table.assert_called_once_with("users")

	def test_availability_uses_aggregate_rpc_without_returning_other_bookings(self) -> None:
		booking_date = date(2030, 1, 1)
		booked_start = datetime(2030, 1, 1, 9, tzinfo=JAKARTA_TZ)
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[
				{
					"booked_starts": [booked_start.isoformat()],
					"bookings_used": 1,
				}
			]
		)
		user = AuthenticatedUser(
			id="profile-id",
			email="student@student.pradita.ac.id",
		)

		availability = get_availability(supabase, booking_date, 1, user)

		self.assertEqual(availability.bookings_used, 1)
		self.assertEqual(availability.bookings_remaining, 1)
		self.assertFalse(availability.slots[1].available)
		supabase.rpc.assert_called_once_with(
			"get_booking_availability",
			{
				"booking_date": "2030-01-01",
				"requested_room": 1,
				"excluded_appointment_id": None,
			},
		)
		supabase.table.assert_not_called()

	def test_supabase_client_uses_per_request_auth_headers(self) -> None:
		with patch("app.database.create_client") as create_client:
			create_supabase_client("first-user-token")
			first_options = create_client.call_args.kwargs["options"]
			create_supabase_client("second-user-token")
			second_options = create_client.call_args.kwargs["options"]
			create_supabase_client()
			public_options = create_client.call_args.kwargs["options"]

		self.assertEqual(
			first_options.headers["Authorization"],
			"Bearer first-user-token",
		)
		self.assertEqual(
			second_options.headers["Authorization"],
			"Bearer second-user-token",
		)
		self.assertNotIn("Authorization", public_options.headers)
		self.assertFalse(first_options.auto_refresh_token)
		self.assertFalse(first_options.persist_session)

	def test_refresh_uses_and_rotates_supabase_auth_session(self) -> None:
		supabase = Mock()
		supabase.auth.refresh_session.return_value.session = SimpleNamespace(
			access_token="new-access-token",
			refresh_token="new-refresh-token",
			expires_in=1800,
		)

		result = renew_tokens("old-refresh-token", supabase)

		self.assertEqual(
			result,
			("new-access-token", "new-refresh-token", 1800),
		)
		supabase.auth.refresh_session.assert_called_once_with(
			refresh_token="old-refresh-token"
		)

	def test_google_callback_exchanges_id_token_and_sets_supabase_cookies(self) -> None:
		google_credentials = Credentials(
			token="google-calendar-access-token",
			refresh_token="google-calendar-refresh-token",
			id_token="verified-google-id-token",
		)
		flow = Mock()
		flow.credentials = google_credentials
		public_supabase = Mock()
		auth_session = SimpleNamespace(
			access_token="supabase-access-token",
			refresh_token="supabase-refresh-token",
			expires_in=2400,
		)
		auth_user = SimpleNamespace(
			email="student@student.pradita.ac.id",
			email_confirmed_at="2026-01-01T00:00:00Z",
		)
		public_supabase.auth.sign_in_with_id_token.return_value = SimpleNamespace(
			session=auth_session,
			user=auth_user,
		)
		user_supabase = Mock()
		profile_rpc = Mock()
		profile_rpc.execute.return_value = SimpleNamespace(data="profile-id")
		store_rpc = Mock()
		store_rpc.execute.return_value = SimpleNamespace(data=None)
		user_supabase.rpc.side_effect = [profile_rpc, store_rpc]
		user_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
			SimpleNamespace(data=[{"nim": 123456, "major": "IT"}])
		)
		request = Request(
			{
				"type": "http",
				"method": "GET",
				"path": "/api/v1/google-auth/oauth2callback",
				"query_string": b"state=oauth-state&code=oauth-code",
				"headers": [],
			}
		)

		with (
			patch("app.api.v1.google_auth.oauth_helper.create_flow", return_value=flow),
			patch(
				"app.api.v1.google_auth.oauth_helper.id_token.verify_oauth2_token",
				return_value={
					"sub": "google-subject",
					"email": "student@student.pradita.ac.id",
					"email_verified": True,
					"name": "Student",
				},
			),
			patch(
				"app.api.v1.google_auth.oauth_helper.create_supabase_client",
				return_value=user_supabase,
			) as create_user_client,
			patch(
				"app.api.v1.google_auth.oauth_helper.encrypt_refresh_token",
				return_value="encrypted-google-refresh-token",
			),
			patch.object(settings, "GOOGLE_CLIENT_ID", "google-client-id"),
			patch.object(settings, "FRONTEND_URL", "https://frontend.example"),
			patch.object(settings, "COOKIE_SECURE", True),
		):
			response = complete_google_oauth(request, public_supabase, "oauth-state")

		public_supabase.auth.sign_in_with_id_token.assert_called_once_with(
			{"provider": "google", "token": "verified-google-id-token"}
		)
		create_user_client.assert_called_once_with("supabase-access-token")
		store_rpc.execute.assert_called_once()
		cookies = response.headers.getlist("set-cookie")
		self.assertEqual(response.status_code, 303)
		self.assertIn("/booking-form", response.headers["location"])
		self.assertTrue(any(cookie.startswith("access_token=") for cookie in cookies))
		self.assertTrue(any(cookie.startswith("refresh_token=") for cookie in cookies))
		self.assertTrue(
			any(cookie.startswith("google_access_token=") for cookie in cookies)
		)
		self.assertTrue(any(cookie.startswith("csrf_token=") for cookie in cookies))

	def test_google_callback_fails_closed_for_unmapped_existing_profile(self) -> None:
		flow = Mock()
		flow.credentials = Credentials(
			token="google-calendar-access-token",
			refresh_token="google-calendar-refresh-token",
			id_token="verified-google-id-token",
		)
		supabase = Mock()
		supabase.auth.sign_in_with_id_token.return_value = SimpleNamespace(
			session=SimpleNamespace(
				access_token="supabase-access-token",
				refresh_token="supabase-refresh-token",
				expires_in=2400,
			),
			user=SimpleNamespace(
				email="student@student.pradita.ac.id",
				email_confirmed_at="2026-01-01T00:00:00Z",
			),
		)
		user_supabase = Mock()
		user_supabase.rpc.return_value.execute.side_effect = APIError(
			{
				"code": "P0001",
				"message": "An existing profile requires administrator identity linking",
			}
		)
		request = Request(
			{
				"type": "http",
				"method": "GET",
				"path": "/api/v1/google-auth/oauth2callback",
				"query_string": b"state=oauth-state&code=oauth-code",
				"headers": [],
			}
		)

		with (
			patch("app.api.v1.google_auth.oauth_helper.create_flow", return_value=flow),
			patch(
				"app.api.v1.google_auth.oauth_helper.id_token.verify_oauth2_token",
				return_value={
					"sub": "google-subject",
					"email": "student@student.pradita.ac.id",
					"email_verified": True,
				},
			),
			patch(
				"app.api.v1.google_auth.oauth_helper.create_supabase_client",
				return_value=user_supabase,
			),
			patch.object(settings, "GOOGLE_CLIENT_ID", "google-client-id"),
			patch.object(settings, "FRONTEND_URL", "https://frontend.example"),
		):
			response = complete_google_oauth(request, supabase, "oauth-state")

		self.assertIn("auth_error=account_link_required", response.headers["location"])
		cookies = response.headers.getlist("set-cookie")
		self.assertFalse(any(cookie.startswith("access_token=") for cookie in cookies))
		self.assertFalse(any(cookie.startswith("refresh_token=") for cookie in cookies))
		supabase.auth.sign_in_with_id_token.assert_called_once()


if __name__ == "__main__":
	unittest.main()
