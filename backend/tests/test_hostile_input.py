import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from support import student_user

from app.api.v1.auth.helper import get_current_user
from app.database import get_db, get_public_db
from app.main import app

HEADERS = {"X-CSRF-Token": "c", "Content-Type": "application/json"}


class HostileInputTests(unittest.TestCase):
	"""Found by fuzzing: values the standard library accepts but cannot convert used to answer 500."""

	def setUp(self) -> None:
		app.dependency_overrides[get_db] = app.dependency_overrides[get_public_db] = lambda: MagicMock()
		app.dependency_overrides[get_current_user] = lambda: student_user()
		self.client = TestClient(app, raise_server_exceptions=False, cookies={"access_token": "t", "csrf_token": "c"})

	def tearDown(self) -> None:
		app.dependency_overrides.clear()

	def test_extreme_timestamps_are_a_422_not_a_500(self) -> None:
		for start in ("0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00", "0001-01-01T00:00:00Z"):
			body = '{"room_number": 1, "start_time": "%s"}' % start
			with self.subTest(start=start):
				self.assertEqual(self.client.post("/api/v1/appointments/", content=body, headers=HEADERS).status_code, 422)

	def test_availability_dates_outside_the_booking_window_are_refused(self) -> None:
		for day in ("0001-01-01", "9999-12-31", "2000-01-01", "2100-06-01"):
			with self.subTest(day=day):
				answer = self.client.get("/api/v1/appointments/availability", params={"date": day, "room_number": 1})
				self.assertIn(answer.status_code, (400, 422))
