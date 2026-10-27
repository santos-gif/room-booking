import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.cancel import cancel_appointment
from app.api.v1.appointment.types import AppointmentPayload, JAKARTA_TZ

from support import next_weekday_start, pending_record, student_user


class AppointmentFlowTests(unittest.TestCase):
	def test_cancellation_uses_the_restricted_state_transition_rpc(self) -> None:
		appointment = {
			"id": "appointment-id",
			"booker_id": "user-id",
			"status": "confirmed",
		}
		supabase = Mock()
		(
			supabase.table.return_value.select.return_value
			.eq.return_value.eq.return_value.in_.return_value
			.limit.return_value.execute.return_value
		) = SimpleNamespace(data=[appointment])
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[{**appointment, "status": "cancelled", "sync_status": "synced"}]
		)

		cancel_appointment(
			"appointment-id",
			supabase,
			student_user(),
		)

		# The state change is the restricted RPC, then the cancelled row is deleted right away.
		self.assertEqual(
			[c.args for c in supabase.rpc.call_args_list],
			[
				(
					"update_own_appointment_state",
					{
						"target_appointment_id": "appointment-id",
						"new_status": "cancelled",
						"new_sync_status": "synced",
					},
				),
				("remove_own_cancelled_appointment", {"target_appointment_id": "appointment-id"}),
			],
		)

	def test_appointment_persists_and_syncs_calendar_event(self) -> None:
		start = next_weekday_start(9)
		appointment_id = "8d4f7ca5-6181-4a42-97d4-641827741219"
		event_uuid = "5b3f4a2d9ea748b190d119a67d256a36"
		inserted_record = pending_record(appointment_id, start)
		confirmed_record = {
			**inserted_record,
			"status": "confirmed",
			"sync_status": "synced",
		}
		supabase = Mock()
		table = supabase.table.return_value
		table.insert.return_value.execute.return_value = SimpleNamespace(
			data=[inserted_record]
		)
		supabase.rpc.return_value.execute.return_value = SimpleNamespace(
			data=[confirmed_record]
		)
		payload = AppointmentPayload(room_number=1, start_time=start)
		with (
			patch("app.api.v1.appointment.booking.uuid4", side_effect=[
				appointment_id,
				SimpleNamespace(hex=event_uuid),
			]),
			patch(
				"app.api.v1.appointment.booking.room_calendar_id",
				return_value="room-calendar",
			),
			patch(
				"app.api.v1.appointment.booking_event.create_calendar_event",
				return_value={"id": event_uuid},
			) as create_event,
		):
			result = create_appointment(
				payload,
				supabase,
				student_user(),
			)

		self.assertEqual(result.status, "confirmed")
		self.assertEqual(result.sync_status, "synced")
		supabase.rpc.assert_called_once_with(
			"update_own_appointment_state",
			{
				"target_appointment_id": appointment_id,
				"new_status": "confirmed",
				"new_sync_status": "synced",
			},
		)
		inserted_values = table.insert.call_args.args[0]
		self.assertEqual(inserted_values["booker_id"], "user-id")
		self.assertEqual(inserted_values["room_number"], 1)
		self.assertEqual(
			datetime.fromisoformat(inserted_values["start_time"]).astimezone(
				JAKARTA_TZ
			),
			start,
		)
		event_body = create_event.call_args.args[2]
		self.assertEqual(event_body["start"]["timeZone"], "Asia/Jakarta")
		self.assertEqual(event_body["start"]["dateTime"], start.isoformat())
		self.assertEqual(
			event_body["end"]["dateTime"],
			(start + timedelta(hours=1)).isoformat(),
		)
