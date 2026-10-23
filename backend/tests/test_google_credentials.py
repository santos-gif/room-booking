import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Response
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.google_api.credentials import (
	REFRESH_TIMEOUT_SEC,
	_TimedRequest,
	calendar_credentials,
)
from app.google_api.exceptions import (
	GoogleAuthorizationException,
	GoogleUnavailableException,
)

DEAD = RefreshError("invalid_grant: Token has been expired or revoked.", {"error": "invalid_grant"})
GOOGLE_DOWN = RefreshError("backend_error: try later", {"error": "backend_error"})


def _supabase() -> Mock:
	supabase = Mock()
	supabase.rpc.return_value.execute.return_value = SimpleNamespace(
		data=[{"refresh_token": "encrypted-token", "is_valid": True}]
	)
	return supabase


def _credentials(supabase: Mock, refresh) -> object:
	with (
		patch("app.google_api.credentials.decrypt_refresh_token", return_value="refresh-token"),
		patch("app.google_api.credentials.Credentials.refresh", new=refresh),
	):
		return calendar_credentials(supabase, "user-id", None, None, Response())


def _invalidated(supabase: Mock) -> bool:
	return any(call.args[0] == "invalidate_google_refresh_token" for call in supabase.rpc.call_args_list)


class RefreshVerdictTests(unittest.TestCase):
	def test_only_invalid_grant_kills_the_stored_token(self) -> None:
		supabase = _supabase()
		with self.assertRaises(GoogleAuthorizationException):
			_credentials(supabase, Mock(side_effect=DEAD))
		self.assertTrue(_invalidated(supabase))

	def test_google_errors_other_than_invalid_grant_keep_the_token(self) -> None:
		for failure in (GOOGLE_DOWN, TransportError("timed out")):
			with self.subTest(failure=type(failure).__name__):
				supabase = _supabase()
				refresh = Mock(side_effect=failure)
				with self.assertRaises(GoogleUnavailableException) as caught:
					_credentials(supabase, refresh)
				self.assertEqual(caught.exception.status_code, 503)
				self.assertEqual(refresh.call_count, 2)
				self.assertFalse(_invalidated(supabase))

	def test_one_hiccup_is_retried_and_the_booking_goes_on(self) -> None:
		supabase = _supabase()
		calls = []

		def refresh(self, request) -> None:
			calls.append(request)
			if len(calls) == 1:
				raise TransportError("timed out")
			self.token = "fresh-access-token"
			self.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

		credentials = _credentials(supabase, refresh)
		self.assertEqual(credentials.token, "fresh-access-token")
		self.assertEqual(len(calls), 2)
		self.assertFalse(_invalidated(supabase))

	def test_google_401s_are_marked_so_the_frontend_forces_a_reconnect(self) -> None:
		with self.assertRaises(GoogleAuthorizationException) as caught:
			_credentials(_supabase(), Mock(side_effect=DEAD))
		self.assertEqual(caught.exception.status_code, 401)
		self.assertEqual(caught.exception.headers, {"X-Reconnect-Google": "1"})

	def test_a_dead_token_is_not_retried(self) -> None:
		refresh = Mock(side_effect=DEAD)
		with self.assertRaises(GoogleAuthorizationException):
			_credentials(_supabase(), refresh)
		self.assertEqual(refresh.call_count, 1)


class RefreshTimeoutTests(unittest.TestCase):
	def test_every_token_call_carries_the_short_timeout(self) -> None:
		with patch.object(GoogleAuthRequest, "__call__", return_value="ok") as send:
			_TimedRequest()("https://oauth2.googleapis.com/token", method="POST")
		self.assertEqual(send.call_args.kwargs["timeout"], REFRESH_TIMEOUT_SEC)


if __name__ == "__main__":
	unittest.main()
