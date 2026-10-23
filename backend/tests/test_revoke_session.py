import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.auth.revoke import revoke_session

CREATE = "app.api.v1.auth.revoke.create_supabase_client"


class RevokeSessionTests(unittest.TestCase):
	def test_refresh_token_is_traded_for_a_fresh_session_which_is_then_revoked_globally(self) -> None:
		client = MagicMock()
		client.auth.refresh_session.return_value = SimpleNamespace(session=SimpleNamespace(access_token="fresh"))
		with patch(CREATE, return_value=client):
			self.assertTrue(revoke_session("expired-access", "refresh"))
		client.auth.refresh_session.assert_called_once_with("refresh")
		# The fresh token, not the expired one: sign-out with an expired JWT is what silently failed before.
		client.auth.admin.sign_out.assert_called_once_with("fresh", "global")

	def test_without_a_refresh_token_the_access_token_is_revoked(self) -> None:
		client = MagicMock()
		with patch(CREATE, return_value=client):
			self.assertTrue(revoke_session("access", None))
		client.auth.refresh_session.assert_not_called()
		client.auth.admin.sign_out.assert_called_once_with("access", "global")

	def test_nothing_to_revoke_without_cookies(self) -> None:
		with patch(CREATE, return_value=MagicMock()):
			self.assertFalse(revoke_session(None, None))

	def test_a_failed_refresh_still_revokes_the_access_token(self) -> None:
		client = MagicMock()
		client.auth.refresh_session.side_effect = RuntimeError("refresh token already used by another tab")
		with patch(CREATE, return_value=client), self.assertLogs("app.api.v1.auth.revoke", level="WARNING"):
			self.assertTrue(revoke_session("still-valid-access", "r"))
		client.auth.admin.sign_out.assert_called_once_with("still-valid-access", "global")

	def test_supabase_failure_is_swallowed_so_logout_still_clears_cookies(self) -> None:
		client = MagicMock()
		client.auth.admin.sign_out.side_effect = RuntimeError("supabase down")
		with patch(CREATE, return_value=client), self.assertLogs("app.api.v1.auth.revoke", level="WARNING"):
			self.assertFalse(revoke_session("a", None))
