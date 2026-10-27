import unittest
from unittest.mock import patch, sentinel

from fastapi import HTTPException

from app.api.v1.appointment.router import reconcile_calendar
from app.google_api.exceptions import GoogleConfigurationException
from app.config import (
	settings,
	validate_integration_configuration,
	validate_security_secrets,
)


class ConfigTests(unittest.IsolatedAsyncioTestCase):
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

	def test_integration_configuration_names_both_room_calendars(self) -> None:
		with (
			patch.object(settings, "SUPABASE_URL", ""),
			patch.object(settings, "SUPABASE_KEY", ""),
			patch.object(settings, "GOOGLE_CLIENT_ID", ""),
			patch.object(settings, "GOOGLE_CLIENT_SECRET", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", ""),
			patch.object(settings, "GOOGLE_CALENDAR_ID", "legacy-calendar"),
			patch.object(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", ""),
		):
			with self.assertRaises(RuntimeError) as error:
				validate_integration_configuration()
			message = str(error.exception)
			self.assertIn("GOOGLE_CALENDAR_ROOM_1_ID", message)
			self.assertIn("GOOGLE_CALENDAR_ROOM_2_ID", message)
			self.assertIn("GOOGLE_CALENDAR_ID is not used", message)

	def test_integration_configuration_rejects_an_unusable_service_account_key(self) -> None:
		with (
			patch.object(settings, "SUPABASE_URL", "https://example.supabase.co"),
			patch.object(settings, "SUPABASE_KEY", "test-key"),
			patch.object(settings, "GOOGLE_CLIENT_ID", "test-client-id"),
			patch.object(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
			patch.object(settings, "GOOGLE_REDIRECT_URI", "http://localhost/callback"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", "room-1"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", "room-2"),
			patch.object(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "not json"),
			patch.object(settings, "SUPABASE_BACKEND_RPC_SECRET", "rpc-secret"),
		):
			with self.assertRaises(GoogleConfigurationException):
				validate_integration_configuration()
