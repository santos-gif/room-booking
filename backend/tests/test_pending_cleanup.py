import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.v1.appointment.reconcile import reconcile_appointments
from app.google_api.exceptions import GoogleAuthorizationException, GoogleCalendarOperationException


class PendingCleanupTests(unittest.TestCase):
	def _reconcile_pending(self, age: timedelta, delete_effect: object = None):
		created = datetime.now(timezone.utc) - age
		row = {
			"id": "appointment-id",
			"booker_id": "user-id",
			"room_number": 1,
			"start_time": (created + timedelta(days=1)).isoformat(),
			"end_time": (created + timedelta(days=1, hours=1)).isoformat(),
			"google_calendar_id": "room-calendar",
			"google_event_id": "event-id",
			"status": "pending",
			"sync_status": "failed",
			"created_at": created.isoformat(),
		}

		def rpc(name: str, params: dict[str, object]) -> Mock:
			call = Mock()
			call.execute.return_value = SimpleNamespace(
				data=[row] if name == "list_reconciliation_appointments" else True
			)
			return call

		supabase = Mock()
		supabase.rpc.side_effect = rpc
		with (
			patch("app.api.v1.appointment.reconcile.delete_calendar_event", side_effect=delete_effect) as delete,
			patch("app.api.v1.appointment.reconcile_sync.create_calendar_event") as create,
		):
			result = reconcile_appointments(supabase)
		return result, supabase, delete, create

	def test_stale_pending_booking_is_undone_never_promoted(self) -> None:
		result, supabase, delete, create = self._reconcile_pending(timedelta(minutes=10))

		self.assertEqual(result.released, 1)
		delete.assert_called_once()
		self.assertEqual(delete.call_args.args[2:4], ("room-calendar", "event-id"))
		create.assert_not_called()
		discard = [c for c in supabase.rpc.call_args_list if c.args[0] == "discard_stale_pending_appointment"]
		self.assertEqual(len(discard), 1)

	def test_recent_pending_booking_is_left_to_its_request(self) -> None:
		result, supabase, delete, _ = self._reconcile_pending(timedelta(seconds=30))

		self.assertEqual(result.released, 0)
		delete.assert_not_called()

	def test_revoked_google_access_still_releases_the_slot(self) -> None:
		with self.assertLogs("app.api.v1.appointment.reconcile", level="WARNING"):
			result, _, _, _ = self._reconcile_pending(
				timedelta(minutes=10), GoogleAuthorizationException("revoked")
			)
		self.assertEqual((result.released, result.failed), (1, 0))

	def test_failed_event_cleanup_keeps_the_row_for_retry(self) -> None:
		result, supabase, _, _ = self._reconcile_pending(
			timedelta(minutes=10), GoogleCalendarOperationException()
		)

		self.assertEqual(result.failed, 1)
		names = [c.args[0] for c in supabase.rpc.call_args_list]
		self.assertNotIn("discard_stale_pending_appointment", names)
