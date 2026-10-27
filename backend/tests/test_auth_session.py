import base64
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Response

from app.api.v1.auth.exceptions import CredentialsException
from app.api.v1.auth.helper import MAX_SESSION_AGE, get_current_user, renew_tokens
from app.database import create_supabase_client


class AuthSessionTests(unittest.IsolatedAsyncioTestCase):
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
						"major": "Information Technology",
					}
				]
			)
		)

		user = get_current_user(supabase, "supabase-access-token")

		self.assertEqual(user.id, "legacy-profile-id")
		supabase.auth.get_user.assert_called_once_with("supabase-access-token")
		supabase.rpc.assert_called_once_with("current_profile_id")
		supabase.table.assert_called_once_with("users")

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

	def _renew_with_sign_in_age(self, days: float | None, *, bare_token: bool = False) -> tuple[str, str, int]:
		"""Renews a session whose Supabase access token says the student signed in `days` ago."""
		claims: dict[str, object] = {"sub": "student"}
		if days is not None:
			claims["amr"] = [{"method": "oauth", "timestamp": int(time.time() - days * 86400)}]
		payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
		supabase = Mock()
		supabase.auth.refresh_session.return_value.session = SimpleNamespace(
			access_token="not-a-jwt" if bare_token else f"header.{payload}.signature",
			refresh_token="new-refresh-token",
			expires_in=1800,
		)
		return renew_tokens("old-refresh-token", supabase)

	def test_refresh_is_refused_a_week_after_the_real_sign_in(self) -> None:
		with self.assertRaises(CredentialsException):
			self._renew_with_sign_in_age(MAX_SESSION_AGE.days + 1)

	def test_refresh_still_works_inside_the_week(self) -> None:
		self.assertEqual(self._renew_with_sign_in_age(MAX_SESSION_AGE.days - 1)[1], "new-refresh-token")

	def test_refresh_without_a_usable_sign_in_time_is_not_capped(self) -> None:
		# Unknown age must never lock every student out; only a proven old sign-in is refused.
		for days, bare in ((None, False), (0, True)):
			self.assertEqual(self._renew_with_sign_in_age(days, bare_token=bare)[1], "new-refresh-token")

	async def test_logout_clears_all_auth_cookies(self) -> None:
		from app.api.v1.auth.router import logout
		response = Response()
		with patch("app.api.v1.auth.router.revoke_session") as revoke:
			res = await logout(response, access_token="test-access-token", refresh_token="test-refresh-token")
		revoke.assert_called_once_with("test-access-token", "test-refresh-token")
		self.assertEqual(res["message"], "Logged out successfully.")
		cookies = response.headers.getlist("set-cookie")
		self.assertTrue(any("access_token=" in c and 'Max-Age=0' in c for c in cookies))
		self.assertTrue(any("refresh_token=" in c and 'Max-Age=0' in c for c in cookies))
		self.assertTrue(any("csrf_token=" in c and 'Max-Age=0' in c for c in cookies))
