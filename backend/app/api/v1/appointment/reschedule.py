"""Moving a booking: the new one is made first, so a failure never leaves the student with nothing."""
import logging
from datetime import datetime, timezone

from supabase import Client

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.cancel import cancel_appointment, get_own_appointment
from app.api.v1.appointment.exceptions import AppointmentStorageException, CalendarSyncException
from app.api.v1.appointment.slots import to_responses, validate_slot
from app.api.v1.appointment.types import AppointmentResponse, JAKARTA_TZ, ReschedulePayload
from app.api.v1.auth.types import AuthenticatedUser

logger = logging.getLogger(__name__)


def reschedule_appointment(
	appointment_id: str,
	payload: ReschedulePayload,
	supabase: Client,
	current_user: AuthenticatedUser,
) -> AppointmentResponse:
	old_appointment = get_own_appointment(supabase, appointment_id, current_user)
	local_start = validate_slot(payload.start_time, payload.room_number)
	try:
		old_start = datetime.fromisoformat(str(old_appointment["start_time"]))
	except (KeyError, ValueError) as error:
		raise AppointmentStorageException() from error
	if old_start.tzinfo is None:
		old_start = old_start.replace(tzinfo=timezone.utc)
	if (
		old_appointment.get("room_number") == payload.room_number
		and old_start.astimezone(JAKARTA_TZ) == local_start
	):
		rows = to_responses([old_appointment])
		if len(rows) != 1:
			raise AppointmentStorageException()
		return rows[0]
	new_appointment = create_appointment(
		payload,
		supabase,
		current_user,
		replaces_appointment_id=appointment_id,
	)

	def cancel(booking_id: str) -> None:
		cancel_appointment(booking_id, supabase, current_user)

	try:
		cancel(appointment_id)
	except Exception:  # noqa: BLE001 - any failure of the old booking's cancel must undo the new one
		try:
			cancel(new_appointment.id)
		except Exception as compensation_error:  # noqa: BLE001 - nothing more to try: reconciliation decides
			logger.error(
				"Reschedule cleanup failed; both appointments need reconciliation.",
				exc_info=compensation_error,
			)
			raise CalendarSyncException() from compensation_error
		raise
	return new_appointment
