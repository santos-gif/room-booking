import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Response
from support import next_weekday_start, pending_record, student_user

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.exceptions import ProfileIncompleteException
from app.api.v1.appointment.reconcile_sync import sync_row
from app.api.v1.appointment.slots import _calendar_event
from app.api.v1.appointment.types import AppointmentPayload


class CalendarTitleTests(unittest.TestCase):
	def _book(self, user):
		start = next_weekday_start(9)
		supabase = Mock()
		supabase.table.return_value.insert.return_value.execute.return_value = SimpleNamespace(
			data=[pending_record("appointment-id", start)]
		)
		confirmed = {**pending_record("appointment-id", start), "status": "confirmed", "sync_status": "synced"}
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(data=[confirmed])
		with (
			patch("app.api.v1.appointment.booking.room_calendar_id", return_value="room"),
			patch("app.api.v1.appointment.booking.create_calendar_event") as create,
		):
			create_appointment(
				AppointmentPayload(room_number=2, start_time=start), supabase, user, None, None, Response()
			)
		return create

	def test_title_has_room_name_and_nim(self) -> None:
		start = next_weekday_start(9)
		event = _calendar_event("id", 1, start, start + timedelta(hours=1), "Santos Mahasiswa", 2510101051)
		self.assertEqual(event["summary"], "Discussion Room 1-Santos Mahasiswa (2510101051)")

	def test_booking_sends_the_title_to_google(self) -> None:
		create = self._book(student_user())
		self.assertEqual(
			create.call_args.args[4]["summary"], "Discussion Room 2-Santos Mahasiswa (2510101051)"
		)

	def test_blank_name_falls_back_to_email_local_part(self) -> None:
		create = self._book(student_user().model_copy(update={"name": "   "}))
		self.assertEqual(create.call_args.args[4]["summary"], "Discussion Room 2-student (2510101051)")

	def test_missing_nim_is_rejected_before_any_insert(self) -> None:
		user = student_user().model_copy(update={"nim": None})
		supabase = Mock()
		with self.assertRaises(ProfileIncompleteException) as caught:
			create_appointment(
				AppointmentPayload(room_number=1, start_time=next_weekday_start(9)),
				supabase, user, None, None, Response(),
			)
		self.assertEqual(caught.exception.status_code, 403)
		self.assertEqual(caught.exception.detail, "Complete your profile (NIM) before booking.")
		supabase.table.assert_not_called()

	def test_reconcile_fallback_title_and_update_keeps_existing_summary(self) -> None:
		start = next_weekday_start(9)
		row = {
			**pending_record("appointment-id", start),
			"google_calendar_id": "room",
			"google_event_id": "event",
			"status": "confirmed",
			"sync_status": "synced",
		}
		stale = {
			"status": "confirmed",
			"summary": "Discussion Room 1-Santos (123)",
			"start": {"dateTime": "2000-01-01T00:00:00+00:00"},
			"end": {"dateTime": "2000-01-01T01:00:00+00:00"},
		}
		base = "app.api.v1.appointment.reconcile_sync."
		with (
			patch(base + "get_calendar_event", return_value=stale),
			patch(base + "update_calendar_event") as update,
			patch(base + "appointment_queries"),
		):
			self.assertEqual(sync_row(Mock(), row), "synchronized")
		self.assertEqual(update.call_args.args[4]["summary"], "Discussion Room 1-Santos (123)")
		self.assertEqual(_calendar_event("i", 2, start, start)["summary"], "Discussion Room 2")


class BookerNameTests(unittest.TestCase):
	def test_name_is_one_short_clean_line(self) -> None:
		from app.api.v1.appointment.slots import _booker_name

		base = student_user()
		messy = base.model_copy(update={"name": "  Santos\n\tMahasiswa\x07 " + "x" * 100})
		name = _booker_name(messy)
		self.assertEqual(name[:17], "Santos Mahasiswa ")
		self.assertLessEqual(len(name), 60)
		self.assertTrue(name.isprintable())
		blank = base.model_copy(update={"name": "\n\x07"})
		self.assertEqual(_booker_name(blank), base.email.partition("@")[0])
