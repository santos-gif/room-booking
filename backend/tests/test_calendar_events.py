import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from googleapiclient.errors import HttpError

from app.api.v1.appointment.calendar_event import build_calendar_event
from app.api.v1.appointment.types import JAKARTA_TZ
from app.config import settings
from app.google_api.calendar_api import create_calendar_event, room_calendar_id
from app.google_api.exceptions import GoogleCalendarOperationException, GoogleConfigurationException


class CalendarEventTests(unittest.TestCase):
	def test_calendar_event_serializes_jakarta_wall_time_and_zone(self) -> None:
		start = datetime(2026, 10, 9, 19, 0, tzinfo=JAKARTA_TZ)
		event = build_calendar_event(
			"appointment-test-id",
			1,
			start,
			start + timedelta(hours=1),
		)

		self.assertEqual(event["start"]["dateTime"], "2026-10-09T19:00:00+07:00")
		self.assertEqual(event["start"]["timeZone"], "Asia/Jakarta")
		self.assertEqual(event["end"]["dateTime"], "2026-10-09T20:00:00+07:00")

	def test_selected_room_uses_its_configured_calendar(self) -> None:
		with (
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_1_ID", "room-one"),
			patch.object(settings, "GOOGLE_CALENDAR_ROOM_2_ID", "room-two"),
		):
			self.assertEqual(room_calendar_id(1), "room-one")
			self.assertEqual(room_calendar_id(2), "room-two")

			with self.assertRaises(GoogleConfigurationException):
				room_calendar_id(3)

	def _create_event(self, insert_effects: list[object], get_effects: list[object]):
		service = Mock()
		events = service.events.return_value
		events.insert.return_value.execute.side_effect = insert_effects
		events.get.return_value.execute.side_effect = get_effects
		with patch(
			"app.google_api.calendar_api.calendar_service",
			return_value=service,
		):
			result = create_calendar_event("room-calendar", "event-id", {})
		return result, events

	def test_dropped_insert_reply_returns_the_event_google_created(self) -> None:
		result, events = self._create_event([TimeoutError()], [{"id": "event-id"}])

		self.assertEqual(result, {"id": "event-id"})
		events.insert.assert_called_once()
		events.get.assert_called_once_with(calendarId="room-calendar", eventId="event-id")

	def test_dropped_insert_with_missing_event_is_retried_once(self) -> None:
		missing = HttpError(SimpleNamespace(status=404, reason="Not Found"), b"")

		result, events = self._create_event(
			[TimeoutError(), {"id": "event-id"}], [missing]
		)

		self.assertEqual(result, {"id": "event-id"})
		self.assertEqual(events.insert.call_count, 2)

	def test_second_unknown_outcome_is_a_failure(self) -> None:
		missing = HttpError(SimpleNamespace(status=404, reason="Not Found"), b"")

		with self.assertRaises(GoogleCalendarOperationException):
			self._create_event([TimeoutError(), TimeoutError()], [missing, missing])
