import unittest
from datetime import date, datetime
from unittest.mock import ANY, Mock, patch

from fastapi import HTTPException
from postgrest.exceptions import APIError
from support import cancelled_row, staff_user, student_user

from app.api.v1.appointment.types import JAKARTA_TZ
from app.api.v1.staff import closures
from app.api.v1.staff.access import require_staff, staff_db_errors
from app.api.v1.staff.events import INLINE_LIMIT, remove_events
from app.api.v1.staff.types import ClosurePayload
from app.google_api.exceptions import GoogleCalendarOperationException

STAFF = staff_user()
CLOSURE = {"id": "c1", "reason": "AC repair", "start_date": "2030-01-01", "end_date": "2030-01-03"}
EVENTS = "app.api.v1.staff.events."


class AccessTests(unittest.TestCase):
	def test_only_staff_pass_the_role_check(self) -> None:
		self.assertIs(require_staff(STAFF), STAFF)
		with self.assertRaises(HTTPException) as caught:
			require_staff(student_user())
		self.assertEqual(caught.exception.status_code, 403)

	def test_database_errors_become_clean_answers(self) -> None:
		def raised(code: str, message: str = "x") -> HTTPException | APIError:
			try:
				with staff_db_errors():
					raise APIError({"code": code, "message": message})
			except (HTTPException, APIError) as error:
				return error

		self.assertEqual(raised("42501").status_code, 403)
		self.assertEqual(raised("22023").status_code, 422)
		self.assertIn("closed", raised("23514", "The room is closed on that date").detail)
		self.assertIn("weekday", raised("23514", "new row violates check constraint").detail)
		self.assertIsInstance(raised("XX000"), APIError)


class ClosureTests(unittest.TestCase):
	def test_closure_cancels_events_and_marks_them_done(self) -> None:
		payload = ClosurePayload(room_number=1, start_date=date(2030, 1, 1), end_date=date(2030, 1, 3), reason=" AC repair ")
		with (
			patch("app.api.v1.staff.closures.staff_queries.create_closure", return_value=[cancelled_row(1), cancelled_row(2)]),
			patch(EVENTS + "delete_calendar_event", side_effect=[None, GoogleCalendarOperationException()]),
			patch(EVENTS + "staff_queries.mark_synced") as marked,
			self.assertLogs(EVENTS[:-1], level="ERROR"),
		):
			result = closures.create(Mock(), payload)
		self.assertEqual((result.cancelled, result.events_left), (2, 1))
		marked.assert_called_once_with(ANY, ["old1"])  # only the event that really went

	def test_a_long_list_is_finished_by_the_nightly_job(self) -> None:
		rows = [cancelled_row(n) for n in range(INLINE_LIMIT + 5)]
		with patch(EVENTS + "delete_calendar_event") as delete, patch(EVENTS + "staff_queries.mark_synced"):
			left = remove_events(Mock(), rows)
		self.assertEqual((delete.call_count, left), (INLINE_LIMIT, 5))

	def test_payload_rejects_backwards_or_huge_ranges(self) -> None:
		for start, end in ((date(2030, 1, 3), date(2030, 1, 1)), (date(2030, 1, 1), date(2032, 1, 1))):
			with self.assertRaises(ValueError):
				ClosurePayload(room_number=1, start_date=start, end_date=end, reason="x")

	def test_preview_asks_for_the_whole_jakarta_days(self) -> None:
		with patch("app.api.v1.staff.closures.staff_queries.list_bookings", return_value=[]) as listed:
			closures.preview(Mock(), 2, date(2030, 1, 1), date(2030, 1, 3))
		_, room, first, after_last, future_only = listed.call_args.args
		self.assertEqual((room, future_only), (2, True))
		self.assertEqual(first, datetime(2030, 1, 1, tzinfo=JAKARTA_TZ))
		self.assertEqual(after_last, datetime(2030, 1, 4, tzinfo=JAKARTA_TZ))


if __name__ == "__main__":
	unittest.main()
