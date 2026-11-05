import unittest
from unittest.mock import MagicMock

from app.queries import staff as staff_queries


class NoticeQueryTests(unittest.TestCase):
	def test_lists_only_unseen_notices_newest_first(self) -> None:
		supabase = MagicMock()
		select = supabase.table.return_value.select.return_value
		ordered = select.is_.return_value.order.return_value
		ordered.limit.return_value.execute.return_value.data = [{"id": "n1", "message": "m"}]

		rows = staff_queries.list_notices(supabase)

		self.assertEqual(rows, [{"id": "n1", "message": "m"}])
		supabase.table.assert_called_once_with("booking_notices")
		select.is_.assert_called_once_with("seen_at", "null")
		select.is_.return_value.order.assert_called_once_with("created_at", desc=True)

	def test_dismissing_stamps_only_the_given_notice(self) -> None:
		supabase = MagicMock()
		update = supabase.table.return_value.update

		staff_queries.dismiss_notice(supabase, "n1")

		self.assertIn("seen_at", update.call_args.args[0])
		update.return_value.eq.assert_called_once_with("id", "n1")


if __name__ == "__main__":
	unittest.main()
