import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1.google_auth.callback import complete_google_oauth
from app.api.v1.google_auth.router import oauth2callback
from app.config import settings
from app.google_api.exceptions import GoogleCredentialException, GoogleRefreshConsentException
from app.main import app


class CallbackRedirectTests(unittest.IsolatedAsyncioTestCase):
	def _run(self, claims=None, fetch_error=None):
		flow = Mock()
		flow.fetch_token.side_effect = fetch_error
		flow.credentials = SimpleNamespace(token="t", refresh_token="r", id_token="idt")
		with (
			patch("app.api.v1.google_auth.callback.create_flow", return_value=flow),
			patch("app.api.v1.google_auth.callback.Credentials", SimpleNamespace),
			patch(
				"app.google_api.oauth.id_token.verify_oauth2_token",
				return_value={"sub": "s", **(claims or {})},
			),
			patch.object(settings, "GOOGLE_CLIENT_ID", "cid"),
			patch.object(settings, "FRONTEND_URL", "https://frontend.example"),
		):
			return complete_google_oauth("s", "c", None, Mock(), "s", "v")

	def test_bad_emails_map_to_the_right_codes(self) -> None:
		cases = [
			({"email": None, "email_verified": True}, "verified_email_required"),
			({"email_verified": True}, "verified_email_required"),
			({"email": "a@student.pradita.ac.id", "email_verified": False}, "verified_email_required"),
			({"email": "not-an-email", "email_verified": True}, "university_email_required"),
			({"email": "a@gmail.com", "email_verified": True}, "university_email_required"),
		]
		for claims, code in cases:
			self.assertIn(f"auth_error={code}", self._run(claims).headers["location"], claims)

	def test_unticked_calendar_scope_warning_needs_consent(self) -> None:
		response = self._run(fetch_error=Warning("Scope has changed"))
		self.assertIn("auth_error=calendar_consent_required", response.headers["location"])

	async def _callback(self, effect):
		with (
			patch("app.api.v1.google_auth.router.complete_google_oauth", side_effect=effect),
			patch.object(settings, "FRONTEND_URL", "https://frontend.example"),
		):
			return await oauth2callback(Mock(), "s", "c", None, "s", "v")

	async def test_unexpected_errors_redirect_instead_of_raising(self) -> None:
		for effect in (RuntimeError("boom"), GoogleCredentialException("x")):
			with self.assertLogs("app.api.v1.google_auth.router", level="ERROR"):
				response = await self._callback(effect)
			self.assertIn("auth_error=google_exchange_failed", response.headers["location"])

	async def test_missing_refresh_consent_redirects(self) -> None:
		response = await self._callback(GoogleRefreshConsentException())
		self.assertIn("auth_error=calendar_consent_required", response.headers["location"])


class AppHandlerTests(unittest.TestCase):
	def test_unhandled_error_returns_generic_500_json(self) -> None:
		@app.get("/_boom")
		def boom():
			raise RuntimeError("secret internals")

		client = TestClient(app, raise_server_exceptions=False)
		with self.assertLogs("app.main", level="ERROR"):
			response = client.get("/_boom")
		self.assertEqual(response.status_code, 500)
		self.assertEqual(response.json(), {"detail": "Internal server error."})
		app.router.routes.pop()

	def test_csrf_bypass_matches_only_the_callback_path(self) -> None:
		client = TestClient(app, raise_server_exceptions=False, cookies={"access_token": "a"})
		response = client.post("/api/v1/google-auth/other-callback")
		self.assertEqual(response.status_code, 403)
