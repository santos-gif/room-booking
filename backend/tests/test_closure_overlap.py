import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.api.v1.staff import closures
from app.api.v1.staff.access import CLOSURE_OVERLAP, staff_db_errors
from app.api.v1.staff.types import ClosurePayload
from app.queries import staff as staff_queries

PAYLOAD = ClosurePayload(room_number=1, start_date=date(2030, 1, 1), end_date=date(2030, 1, 3), reason="AC")
QUERIES = "app.api.v1.staff.closures.staff_queries"


def db_refusal(message: str) -> HTTPException:
	try:
		with staff_db_errors():
			raise APIError({"code": "23P01", "message": message})
	except HTTPException as error:
		return error
	raise AssertionError("the database error was not translated")


class ClosureOverlapTests(unittest.TestCase):
	def test_an_overlapping_closure_is_refused_before_anything_is_cancelled(self) -> None:
		with (
			patch(f"{QUERIES}.overlapping_closure", return_value={"id": "c1"}),
			patch(f"{QUERIES}.create_closure") as create,
			self.assertRaises(HTTPException) as caught,
		):
			closures.create(MagicMock(), PAYLOAD)

		self.assertEqual(caught.exception.status_code, 409)
		self.assertEqual(caught.exception.detail, CLOSURE_OVERLAP)
		create.assert_not_called()

	def test_free_dates_are_closed_as_before(self) -> None:
		with (
			patch(f"{QUERIES}.overlapping_closure", return_value=None),
			patch(f"{QUERIES}.create_closure", return_value=[]) as create,
			patch("app.api.v1.staff.closures.remove_events", return_value=0),
		):
			result = closures.create(MagicMock(), PAYLOAD)

		self.assertEqual(result.cancelled, 0)
		create.assert_called_once()

	def test_the_closure_constraint_reads_as_an_overlap_not_a_taken_slot(self) -> None:
		refusal = db_refusal('violates exclusion constraint "room_closures_no_overlap"')
		self.assertEqual((refusal.status_code, refusal.detail), (409, CLOSURE_OVERLAP))

	def test_the_booking_constraint_still_reads_as_a_taken_slot(self) -> None:
		refusal = db_refusal('violates exclusion constraint "appointments_room_time_no_overlap"')
		self.assertEqual(refusal.detail, "That slot was just taken. Try again.")

	def test_the_query_looks_for_any_shared_day(self) -> None:
		supabase = MagicMock()
		chain = supabase.table.return_value.select.return_value.eq.return_value
		limited = chain.lte.return_value.gte.return_value.limit.return_value
		limited.execute.return_value.data = [{"id": "c1"}]

		found = staff_queries.overlapping_closure(supabase, 1, date(2030, 1, 1), date(2030, 1, 3))

		self.assertEqual(found, {"id": "c1"})
		chain.lte.assert_called_once_with("start_date", "2030-01-03")
		chain.lte.return_value.gte.assert_called_once_with("end_date", "2030-01-01")


if __name__ == "__main__":
	unittest.main()
