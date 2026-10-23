import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.api.v1.google_auth.callback_identity import is_allowed_email
from app.api.v1.google_auth.login import create_google_login_response
from app.config import settings


class GoogleOAuthTests(unittest.TestCase):
	def test_google_email_domain_validation_is_exact(self) -> None:
		self.assertTrue(is_allowed_email("student@student.pradita.ac.id"))
		self.assertTrue(is_allowed_email("staff@pradita.ac.id"))
		self.assertFalse(is_allowed_email("user@evil-pradita.ac.id"))
		self.assertFalse(is_allowed_email("user@pradita.ac.id.evil.com"))

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
