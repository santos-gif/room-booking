import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.v1.appointment.reconcile import reconcile_appointments
from app.queries import appointments as queries

R = "app.api.v1.appointment.reconcile"


class PurgeTests(unittest.TestCase):
	def test_purge_calls_the_secret_guarded_function_and_returns_the_count(self) -> None:
		supabase = Mock()
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=7)
		self.assertEqual(queries.purge_finished(supabase), 7)
		self.assertEqual(supabase.rpc.call_args.args[0], "purge_finished_appointments")
		self.assertIn("backend_secret", supabase.rpc.call_args.args[1])

	def test_cron_reports_the_purge_and_survives_its_failure(self) -> None:
		with patch(f"{R}.appointment_queries.list_for_reconciliation", return_value=[]), \
			patch(f"{R}.appointment_queries.purge_finished", return_value=3):
			self.assertEqual(reconcile_appointments(Mock()).purged, 3)
		with patch(f"{R}.appointment_queries.list_for_reconciliation", return_value=[]), \
			patch(f"{R}.appointment_queries.purge_finished", side_effect=RuntimeError("db")), \
			self.assertLogs(R, level="ERROR"):
			self.assertEqual(reconcile_appointments(Mock()).purged, 0)
