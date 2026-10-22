import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.oauth2.credentials import Credentials
from postgrest.exceptions import APIError
from support import oauth_callback_request

from app.api.v1.google_auth.callback import complete_google_oauth
from app.config import settings


class GoogleOAuthTests(unittest.TestCase):
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
			SimpleNamespace(data=[{"nim": 123456, "major": "Information Technology"}])
		)
		request = oauth_callback_request()

		with (
			patch("app.api.v1.google_auth.callback.create_flow", return_value=flow),
			patch(
				"app.google_api.oauth.id_token.verify_oauth2_token",
				return_value={
					"sub": "google-subject",
					"email": "student@student.pradita.ac.id",
					"email_verified": True,
					"name": "Student",
				},
			),
			patch(
				"app.api.v1.google_auth.callback.create_supabase_client",
				return_value=user_supabase,
			) as create_user_client,
			patch(
				"app.api.v1.google_auth.callback.encrypt_refresh_token",
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
		self.assertIn("/my-bookings", response.headers["location"])
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
		request = oauth_callback_request()

		with (
			patch("app.api.v1.google_auth.callback.create_flow", return_value=flow),
			patch(
				"app.google_api.oauth.id_token.verify_oauth2_token",
				return_value={
					"sub": "google-subject",
					"email": "student@student.pradita.ac.id",
					"email_verified": True,
				},
			),
			patch(
				"app.api.v1.google_auth.callback.create_supabase_client",
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
