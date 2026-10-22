import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Response
from supabase import Client

from app.api.v1.appointment.booking import create_appointment
from app.api.v1.appointment.cancel import cancel_appointment, get_own_appointment
from app.api.v1.appointment.exceptions import AppointmentStorageException, CalendarSyncException
from app.api.v1.appointment.slots import _responses, _validate_slot
from app.api.v1.appointment.types import AppointmentResponse, JAKARTA_TZ, ReschedulePayload
from app.api.v1.auth.types import AuthenticatedUser

logger = logging.getLogger(__name__)


def reschedule_appointment(
	appointment_id: str,
	payload: ReschedulePayload,
	supabase: Client,
	current_user: AuthenticatedUser,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> AppointmentResponse:
	old_appointment = get_own_appointment(supabase, appointment_id, current_user)
	local_start = _validate_slot(payload.start_time, payload.room_number)
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
		rows = _responses([old_appointment])
		if len(rows) != 1:
			raise AppointmentStorageException()
		return rows[0]
	new_appointment = create_appointment(
		payload,
		supabase,
		current_user,
		access_token,
		expires_at,
		response,
		replaces_appointment_id=appointment_id,
	)
	try:
		cancel_appointment(
			appointment_id,
			supabase,
			current_user,
			access_token,
			expires_at,
			response,
		)
	except HTTPException as error:
		try:
			cancel_appointment(
				new_appointment.id,
				supabase,
				current_user,
				access_token,
				expires_at,
				response,
			)
		except HTTPException as compensation_error:
			logger.error(
				"Reschedule cleanup failed; both appointments need reconciliation.",
				exc_info=compensation_error,
			)
			raise CalendarSyncException() from compensation_error
		raise error
	return new_appointment
