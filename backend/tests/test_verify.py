import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from support import next_weekday_start, student_user

from app.api.v1.appointment import verify
from app.api.v1.appointment.verify import verify_appointments
from app.google_api.exceptions import GoogleAuthorizationException, GoogleCalendarOperationException

V = "app.api.v1.appointment.verify"
TITLE = "Discussion Room 1-Santos Mahasiswa (2510101051)"


def row(n: int, status: str = "confirmed") -> dict[str, object]:
	start = next_weekday_start(9) + timedelta(days=n)
	return {
		"id": f"id-{n}", "booker_id": "user-id", "room_number": 1, "status": status,
		"sync_status": "synced", "google_calendar_id": "cal", "google_event_id": f"ev-{n}",
		"start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat(),
	}


def run(rows, event=None, side_effect=None, reachable=True):
	"""Run verify with Google mocked; returns (ids kept, get, update, cancel)."""
	with (
		patch(f"{V}.appointment_queries.list_active", return_value=rows),
		patch(f"{V}.appointment_queries.update_own_state") as cancel,
		patch(f"{V}.appointment_queries.remove_own_cancelled") as remove,
		patch(f"{V}.get_calendar_event", side_effect=side_effect, return_value=event) as get,
		patch(f"{V}.update_calendar_event") as update,
		patch(f"{V}.calendar_is_reachable", side_effect=reachable if isinstance(reachable, Exception) else None,
			return_value=reachable) as reach,
	):
		result = verify_appointments(Mock(), student_user())
	run.reach = reach
	run.remove = remove
	return [r.id for r in result], get, update, cancel


class VerifyTests(unittest.TestCase):
	def setUp(self) -> None:
		verify._last_verified.clear()

	def test_deleted_event_cancels_the_row_and_omits_it(self) -> None:
		ids, _, _, cancel = run([row(1)], event=None)
		self.assertEqual(ids, [])
		cancel.assert_called_once_with(unittest.mock.ANY, "id-1", "cancelled", "synced")

	def test_deleted_event_also_deletes_the_row_and_survives_a_failed_delete(self) -> None:
		run([row(1)], event=None)
		run.remove.assert_called_once_with(unittest.mock.ANY, "id-1")
		verify._last_verified.clear()
		with (
			patch(f"{V}.appointment_queries.list_active", return_value=[row(2)]),
			patch(f"{V}.appointment_queries.update_own_state"),
			patch(f"{V}.appointment_queries.remove_own_cancelled", side_effect=RuntimeError("db")),
			patch(f"{V}.get_calendar_event", return_value=None),
			patch(f"{V}.calendar_is_reachable", return_value=True),
			self.assertLogs(V, level="ERROR"),
		):
			self.assertEqual(verify_appointments(Mock(), student_user()), [])

	def test_cancelled_status_event_is_treated_as_deleted(self) -> None:
		ids, _, _, cancel = run([row(1)], event={"status": "cancelled", "summary": TITLE})
		self.assertEqual(ids, [])
		cancel.assert_called_once()

	def test_existing_event_with_right_title_is_left_alone(self) -> None:
		ids, _, update, cancel = run([row(1)], event={"status": "confirmed", "summary": TITLE})
		self.assertEqual(ids, ["id-1"])
		update.assert_not_called()
		cancel.assert_not_called()

	def test_google_failures_keep_the_row(self) -> None:
		for error in (GoogleCalendarOperationException(), GoogleAuthorizationException("x"), TimeoutError()):
			verify._last_verified.clear()  # each case is a fresh request
			with self.subTest(error=type(error).__name__), self.assertLogs(V, level="ERROR"):
				ids, _, _, cancel = run([row(1)], side_effect=error)
			self.assertEqual(ids, ["id-1"])
			cancel.assert_not_called()

	def test_database_error_on_cancel_keeps_the_row(self) -> None:
		with (
			patch(f"{V}.appointment_queries.list_active", return_value=[row(1)]),
			patch(f"{V}.appointment_queries.update_own_state", side_effect=RuntimeError("db")),
			patch(f"{V}.get_calendar_event", return_value=None),
			self.assertLogs(V, level="ERROR"),
		):
			result = verify_appointments(Mock(), student_user())
		self.assertEqual([r.id for r in result], ["id-1"])

	def test_old_title_is_healed_with_a_full_body(self) -> None:
		ids, _, update, _ = run([row(1)], event={"status": "confirmed", "summary": "Discussion Room 1"})
		self.assertEqual(ids, ["id-1"])
		args = update.call_args.args
		self.assertEqual(args[3], "ev-1")
		self.assertEqual(args[4]["summary"], TITLE)
		self.assertIn("start", args[4])

	def test_failed_title_update_still_lists_the_row(self) -> None:
		with patch(f"{V}.update_calendar_event", side_effect=GoogleCalendarOperationException()):
			with (
				patch(f"{V}.appointment_queries.list_active", return_value=[row(1)]),
				patch(f"{V}.get_calendar_event", return_value={"summary": "old"}),
				self.assertLogs(V, level="ERROR"),
			):
				result = verify_appointments(Mock(), student_user())
		self.assertEqual([r.id for r in result], ["id-1"])

	def test_one_failing_row_does_not_stop_the_next(self) -> None:
		with self.assertLogs(V, level="ERROR"):
			ids, get, _, cancel = run(
				[row(1), row(2), row(3)],
				side_effect=[GoogleCalendarOperationException(), None, {"summary": TITLE}],
			)
		self.assertEqual(ids, ["id-1", "id-3"])
		self.assertEqual(get.call_count, 3)
		cancel.assert_called_once()

	def test_pending_rows_are_never_checked(self) -> None:
		ids, get, _, _ = run([row(1, "pending")])
		self.assertEqual(ids, ["id-1"])
		get.assert_not_called()

	def test_work_is_capped(self) -> None:
		ids, get, _, _ = run([row(n) for n in range(1, 13)], event={"summary": TITLE})
		self.assertEqual(len(ids), 12)
		self.assertEqual(get.call_count, 10)

	def test_plain_list_makes_no_google_call(self) -> None:
		from app.api.v1.appointment.booking import list_appointments

		with (
			patch(f"{V}.get_calendar_event") as get,
			patch("app.api.v1.appointment.booking.appointment_queries.list_active", return_value=[row(1)]),
		):
			result = list_appointments(Mock(), student_user())
		self.assertEqual(len(result), 1)
		get.assert_not_called()
