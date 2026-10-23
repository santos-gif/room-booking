import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from googleapiclient.errors import HttpError
from support import student_user
from types import SimpleNamespace

from app.api.v1.appointment import verify
from app.api.v1.appointment.reconcile import require_cron_secret
from app.config import settings
from app.google_api.calendar_single_event import calendar_is_reachable
from app.google_api.exceptions import GoogleCalendarOperationException
from test_verify import TITLE, V, row, run

SERVICE = "app.google_api.calendar_single_event.calendar_service"


def calendar_answering(status: int | None) -> Mock:
	service = Mock()
	get = service.calendars.return_value.get.return_value.execute
	if status:
		get.side_effect = HttpError(SimpleNamespace(status=status, reason="x"), b"")
	return service


class CalendarGuardTests(unittest.TestCase):
	def setUp(self) -> None:
		verify._last_verified.clear()

	def test_event_gone_and_calendar_reachable_cancels(self) -> None:
		ids, _, _, cancel = run([row(1)], event=None, reachable=True)
		self.assertEqual(ids, [])
		cancel.assert_called_once()

	def test_event_gone_but_calendar_unreachable_keeps_the_row(self) -> None:
		with self.assertLogs(V, level="WARNING"):
			ids, _, _, cancel = run([row(1)], event=None, reachable=False)
		self.assertEqual(ids, ["id-1"])
		cancel.assert_not_called()

	def test_calendar_check_failing_keeps_the_row(self) -> None:
		with self.assertLogs(V, level="ERROR"):
			ids, _, _, cancel = run([row(1)], event=None, reachable=GoogleCalendarOperationException())
		self.assertEqual(ids, ["id-1"])
		cancel.assert_not_called()

	def test_cancelled_event_needs_no_calendar_check(self) -> None:
		ids, _, _, _ = run([row(1)], event={"status": "cancelled"})
		self.assertEqual(ids, [])
		run.reach.assert_not_called()

	def test_reachability_by_http_status(self) -> None:
		for status, expected in ((None, True), (404, False), (403, False), (410, False)):
			with patch(SERVICE, return_value=calendar_answering(status)):
				self.assertIs(calendar_is_reachable(Mock(), "u", "cal"), expected)
		with patch(SERVICE, return_value=calendar_answering(503)), self.assertRaises(
			GoogleCalendarOperationException
		):
			calendar_is_reachable(Mock(), "u", "cal")


class CooldownTests(unittest.TestCase):
	def setUp(self) -> None:
		verify._last_verified.clear()

	def test_second_call_within_30_seconds_makes_no_google_call(self) -> None:
		with patch(f"{V}.time.monotonic", return_value=100.0):
			_, first, _, _ = run([row(1)], event={"summary": TITLE})
			ids, second, _, _ = run([row(1)], event={"summary": TITLE})
		self.assertEqual(first.call_count, 1)
		self.assertEqual(ids, ["id-1"])
		second.assert_not_called()

	def test_call_after_the_cooldown_verifies_again(self) -> None:
		with patch(f"{V}.time.monotonic", return_value=0.0) as clock:
			run([row(1)], event={"summary": TITLE})
			clock.return_value = 31.0
			_, get, _, _ = run([row(1)], event={"summary": TITLE})
		self.assertEqual(get.call_count, 1)

	def test_users_do_not_share_a_cooldown(self) -> None:
		self.assertFalse(verify._on_cooldown("a"))
		self.assertFalse(verify._on_cooldown("b"))
		self.assertTrue(verify._on_cooldown("a"))

	def test_table_stays_bounded(self) -> None:
		verify._last_verified.update({str(n): -1000.0 for n in range(1001)})
		verify._on_cooldown("new")
		self.assertEqual(list(verify._last_verified), ["new"])


class CronSecretTests(unittest.TestCase):
	def test_non_ascii_header_is_a_401_not_a_crash(self) -> None:
		with patch.object(settings, "CRON_SECRET", "s" * 32):
			with self.assertRaises(HTTPException) as raised:
				require_cron_secret("Bearer sécret")
			self.assertEqual(raised.exception.status_code, 401)
			require_cron_secret("Bearer " + "s" * 32)
