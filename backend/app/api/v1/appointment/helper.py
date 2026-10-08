import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException, Response
from postgrest.exceptions import APIError
from pydantic import TypeAdapter, ValidationError
from postgrest.types import JSON
from supabase import Client

from app.api.v1.appointment.exceptions import (
	AppointmentConflictException,
	AppointmentNotFoundException,
	AppointmentStorageException,
	AppointmentValidationException,
	CalendarSyncException,
	DailyBookingLimitException,
)
from app.api.v1.appointment.types import (
	AppointmentPayload,
	AppointmentResponse,
	AvailabilityResponse,
	AvailableSlot,
	JAKARTA_TZ,
	ReconciliationResponse,
	ReschedulePayload,
)
from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.google_auth.calendar_helper import (
	create_calendar_event,
	delete_calendar_event,
	get_calendar_event,
	room_calendar_id,
	update_calendar_event,
)
from app.api.v1.google_auth.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
)
from app.config import settings
from app.models.appointment import AppointmentRecord

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("pending", "confirmed")
APPOINTMENTS_ADAPTER = TypeAdapter(list[AppointmentRecord])


def _responses(data: object) -> list[AppointmentResponse]:
	try:
		records = APPOINTMENTS_ADAPTER.validate_python(data or [])
		return [
			AppointmentResponse(
				id=record.id,
				booker_id=record.booker_id,
				room_number=cast(Literal[1,2], record.room_number),
				start_time=record.start_time,
				end_time=record.end_time,
				status=record.status,
				sync_status=record.sync_status,
			)
			for record in records
		]
	except ValidationError as error:
		raise AppointmentStorageException() from error


def _validate_slot(start_time: datetime, room_number: int) -> datetime:
	local_start = start_time.astimezone(JAKARTA_TZ)
	if room_number not in (1, 2):
		raise AppointmentValidationException("Choose Discussion Room 1 or 2.")
	if (
		local_start.weekday() > 4
		or not 8 <= local_start.hour < 17
		or local_start.minute != 0
		or local_start.second != 0
		or local_start.microsecond != 0
	):
		raise AppointmentValidationException(
			"Bookings must start on weekdays between 08:00 and 16:00 WIB."
		)
	if local_start <= datetime.now(JAKARTA_TZ):
		raise AppointmentValidationException("Choose a future booking time.")
	return local_start


def _calendar_event(
	appointment_id: str,
	room_number: int,
	start_time: datetime,
	end_time: datetime,
) -> dict[str, object]:
	return {
		"summary": f"Discussion Room {room_number} booking",
		"description": f"Room booking appointment ID: {appointment_id}",
		"start": {
			"dateTime": start_time.isoformat(),
			"timeZone": "Asia/Jakarta",
		},
		"end": {
			"dateTime": end_time.isoformat(),
			"timeZone": "Asia/Jakarta",
		},
	}


def list_appointments(
	supabase: Client,
	current_user: AuthenticatedUser,
) -> list[AppointmentResponse]:
	result = (
		supabase.table("appointments")
		.select("*")
		.eq("booker_id", current_user.id)
		.in_("status", list(ACTIVE_STATUSES))
		.gte("start_time", datetime.now(timezone.utc).isoformat())
		.order("start_time")
		.execute()
	)
	return _responses(result.data)


def get_availability(
	supabase: Client,
	booking_date: date,
	room_number: int,
	current_user: AuthenticatedUser,
	exclude_appointment_id: str | None = None,
) -> AvailabilityResponse:
	if room_number not in (1, 2):
		raise AppointmentValidationException("Choose Discussion Room 1 or 2.")
	day_start = datetime.combine(booking_date, time.min, tzinfo=JAKARTA_TZ)
	day_end = day_start + timedelta(days=1)
	result = (
		supabase.table("appointments")
		.select("id,start_time,booker_id,room_number")
		.in_("status", list(ACTIVE_STATUSES))
		.gte("start_time", day_start.astimezone(timezone.utc).isoformat())
		.lt("start_time", day_end.astimezone(timezone.utc).isoformat())
		.execute()
	)
	booked_starts = {
		datetime.fromisoformat(row["start_time"]).astimezone(JAKARTA_TZ)
		for row in result.data
		if isinstance(row, dict)
		and row.get("room_number") == room_number
		and isinstance(row.get("start_time"), str)
		and row.get("id") != exclude_appointment_id
	}
	bookings_used = sum(
		1 for row in result.data if isinstance(row, dict)
		and row.get("booker_id") == current_user.id
		and row.get("id") != exclude_appointment_id
	)
	if exclude_appointment_id:
		_get_own_appointment(supabase, exclude_appointment_id, current_user)
	now = datetime.now(JAKARTA_TZ)
	slots = [
		AvailableSlot(
			start_time=slot,
			end_time=slot + timedelta(hours=1),
			available=(
				booking_date.weekday() < 5
				and slot not in booked_starts
				and slot > now
				and bookings_used < 2
			),
		)
		for hour in range(8, 17)
		for slot in [datetime.combine(booking_date, time(hour), tzinfo=JAKARTA_TZ)]
	]
	return AvailabilityResponse(
		bookings_used=bookings_used,
		bookings_remaining=max(0, 2 - bookings_used),
		slots=slots,
	)


def create_appointment(
	payload: AppointmentPayload,
	supabase: Client,
	current_user: AuthenticatedUser,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
	replaces_appointment_id: str | None = None,
) -> AppointmentResponse:
	start_time = _validate_slot(payload.start_time, payload.room_number)
	end_time = start_time + timedelta(hours=1)
	calendar_id = room_calendar_id(payload.room_number)
	appointment_id = str(uuid4())
	event_id = uuid4().hex
	values: JSON = {
		"id": appointment_id,
		"booker_id": current_user.id,
		"room_number": payload.room_number,
		"start_time": start_time.astimezone(timezone.utc).isoformat(),
		"end_time": end_time.astimezone(timezone.utc).isoformat(),
		"google_calendar_id": calendar_id,
		"google_event_id": event_id,
		"status": "pending",
		"sync_status": "pending",
	}
	if replaces_appointment_id:
		values["replaces_appointment_id"] = replaces_appointment_id
	try:
		created = supabase.table("appointments").insert(values).execute()
	except APIError as error:
		if error.code == "23P01":
			raise AppointmentConflictException() from error
		if error.code == "P0001":
			raise DailyBookingLimitException() from error
		if error.code == "23505":
			raise AppointmentConflictException() from error
		logger.exception("Database rejected appointment reservation.")
		raise AppointmentStorageException() from error
	rows = _responses(created.data)
	if len(rows) != 1:
		raise AppointmentStorageException()
	try:
		create_calendar_event(
			supabase,
			current_user.id,
			calendar_id,
			event_id,
			_calendar_event(appointment_id, payload.room_number, start_time, end_time),
			access_token,
			expires_at,
			response,
		)
	except GoogleAuthorizationException:
		supabase.table("appointments").update(
			{"sync_status": "failed"}
		).eq("id", appointment_id).execute()
		raise
	except GoogleCalendarOperationException as error:
		supabase.table("appointments").update(
			{"sync_status": "failed"}
		).eq("id", appointment_id).execute()
		logger.exception("Google Calendar event creation failed.")
		raise CalendarSyncException() from error
	try:
		updated = (
			supabase.table("appointments")
			.update({"status": "confirmed", "sync_status": "synced"})
			.eq("id", appointment_id)
			.execute()
		)
	except APIError as error:
		logger.exception("Calendar event exists but booking confirmation failed.")
		raise CalendarSyncException() from error
	rows = _responses(updated.data)
	if len(rows) != 1:
		raise CalendarSyncException()
	return rows[0]


def reschedule_appointment(
	appointment_id: str,
	payload: ReschedulePayload,
	supabase: Client,
	current_user: AuthenticatedUser,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> AppointmentResponse:
	old_appointment = _get_own_appointment(supabase, appointment_id, current_user)
	local_start = _validate_slot(payload.start_time, payload.room_number)
	old_start = datetime.fromisoformat(str(old_appointment["start_time"]))
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


def _get_own_appointment(
	supabase: Client,
	appointment_id: str,
	current_user: AuthenticatedUser,
) -> dict[str, object]:
	result = (
		supabase.table("appointments")
		.select("*")
		.eq("id", appointment_id)
		.eq("booker_id", current_user.id)
		.in_("status", list(ACTIVE_STATUSES))
		.limit(1)
		.execute()
	)
	if not result.data or not isinstance(result.data[0], dict):
		raise AppointmentNotFoundException()
	return cast(dict[str,object],result.data[0])


def cancel_appointment(
	appointment_id: str,
	supabase: Client,
	current_user: AuthenticatedUser,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> None:
	appointment = _get_own_appointment(supabase, appointment_id, current_user)
	calendar_id = appointment.get("google_calendar_id")
	event_id = appointment.get("google_event_id")
	if isinstance(calendar_id, str) and isinstance(event_id, str):
		try:
			delete_calendar_event(
				supabase,
				current_user.id,
				calendar_id,
				event_id,
				access_token,
				expires_at,
				response,
			)
		except GoogleAuthorizationException:
			raise
		except GoogleCalendarOperationException as error:
			logger.exception("Could not delete the room calendar event.")
			raise CalendarSyncException() from error
	try:
		result = (
			supabase.table("appointments")
			.update({"status": "cancelled", "sync_status": "synced"})
			.eq("id", appointment_id)
			.eq("booker_id", current_user.id)
			.execute()
		)
	except APIError as error:
		logger.exception("Google event was deleted but booking cancellation failed.")
		raise CalendarSyncException() from error
	if not result.data:
		raise AppointmentStorageException()


def _stored_utc(value: object) -> datetime | None:
	if not isinstance(value, str):
		return None
	try:
		parsed = datetime.fromisoformat(value)
	except ValueError:
		return None
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=timezone.utc)
	return parsed.astimezone(timezone.utc)


def _calendar_time_matches(
	event: dict[str, object],
	field: str,
	expected: object,
) -> bool:
	event_time = event.get(field)
	if not isinstance(event_time, dict):
		return False
	google_value = event_time.get("dateTime")
	actual = _stored_utc(google_value)
	target = _stored_utc(expected)
	return actual is not None and target is not None and actual == target


def reconcile_appointments(supabase: Client) -> ReconciliationResponse:
	result = (
		supabase.table("appointments")
		.select("*")
		.in_("status", list(ACTIVE_STATUSES))
		.execute()
	)
	rows = result.data
	checked = 0
	synchronized = 0
	released = 0
	failed = 0
	for row in rows:
		if not isinstance(row, dict):
			failed += 1
			continue
		checked += 1
		appointment_id = row.get("id")
		user_id = row.get("booker_id")
		calendar_id = row.get("google_calendar_id")
		event_id = row.get("google_event_id")
		room_number = row.get("room_number")
		if (
			row.get("sync_status") == "legacy"
			and isinstance(appointment_id, str)
			and room_number in (1, 2)
		):
			try:
				calendar_id = room_calendar_id(room_number)
				event_id = uuid5(
					NAMESPACE_URL,
					f"discussion-room-booking:{appointment_id}",
				).hex
				supabase.table("appointments").update(
					{
						"google_calendar_id": calendar_id,
						"google_event_id": event_id,
						"sync_status": "pending",
					}
				).eq("id", appointment_id).execute()
			except APIError:
				logger.exception(
					"Could not prepare legacy appointment %s for reconciliation.",
					appointment_id,
				)
				failed += 1
				continue
			row["google_calendar_id"] = calendar_id
			row["google_event_id"] = event_id
			row["sync_status"] = "pending"
		if not all(
			isinstance(value, str)
			for value in (appointment_id, user_id, calendar_id, event_id)
		) or room_number not in (1, 2):
			logger.error("Appointment %r is missing calendar reconciliation data.", appointment_id)
			failed += 1
			continue
		try:
			event = get_calendar_event(
				supabase,
				user_id,
				calendar_id,
				event_id,
				None,
				None,
				Response(),
			)
			if event is None or event.get("status") == "cancelled":
				if (
					event is None
					and row.get("sync_status") in ("pending", "failed")
				):
					event = create_calendar_event(
						supabase,
						user_id,
						calendar_id,
						event_id,
						_calendar_event(
							appointment_id,
							room_number,
							datetime.fromisoformat(row["start_time"]).astimezone(
								JAKARTA_TZ
							),
							datetime.fromisoformat(row["end_time"]).astimezone(
								JAKARTA_TZ
							),
						),
						None,
						None,
						Response(),
					)
				else:
					supabase.table("appointments").update(
						{"status": "cancelled", "sync_status": "synced"}
					).eq("id", appointment_id).execute()
					released += 1
					continue
			if event is None:
				raise GoogleCalendarOperationException()
			start_value = row.get("start_time")
			end_value = row.get("end_time")
			if (
				not _calendar_time_matches(event, "start", start_value)
				or not _calendar_time_matches(event, "end", end_value)
			):
				start = datetime.fromisoformat(str(start_value)).astimezone(JAKARTA_TZ)
				end = datetime.fromisoformat(str(end_value)).astimezone(JAKARTA_TZ)
				update_calendar_event(
					supabase,
					user_id,
					calendar_id,
					event_id,
					_calendar_event(appointment_id, room_number, start, end),
					None,
					None,
					Response(),
				)
			supabase.table("appointments").update(
				{"status": "confirmed", "sync_status": "synced"}
			).eq("id", appointment_id).execute()
			row["status"] = "confirmed"
			row["sync_status"] = "synced"
			synchronized += 1
		except (GoogleAuthorizationException, GoogleCalendarOperationException, APIError):
			logger.exception("Appointment %s could not be reconciled.", appointment_id)
			failed += 1

	for replacement in rows:
		if (
			not isinstance(replacement, dict)
			or replacement.get("status") != "confirmed"
			or replacement.get("sync_status") != "synced"
		):
			continue
		old_id = replacement.get("replaces_appointment_id")
		user_id = replacement.get("booker_id")
		if not isinstance(old_id, str) or not isinstance(user_id, str):
			continue
		try:
			old_result = (
				supabase.table("appointments")
				.select("*")
				.eq("id", old_id)
				.eq("booker_id", user_id)
				.in_("status", list(ACTIVE_STATUSES))
				.limit(1)
				.execute()
			)
			if not old_result.data or not isinstance(old_result.data[0], dict):
				continue
			old = old_result.data[0]
			if isinstance(old.get("google_calendar_id"), str) and isinstance(
				old.get("google_event_id"), str
			):
				delete_calendar_event(
					supabase,
					user_id,
					old["google_calendar_id"],
					old["google_event_id"],
					None,
					None,
					Response(),
				)
			supabase.table("appointments").update(
				{"status": "cancelled", "sync_status": "synced"}
			).eq("id", old_id).eq("booker_id", user_id).execute()
			released += 1
		except (GoogleAuthorizationException, GoogleCalendarOperationException, APIError):
			logger.exception("Rescheduled appointment %s could not be finalized.", old_id)
			failed += 1

	return ReconciliationResponse(
		checked=checked,
		synchronized=synchronized,
		released=released,
		failed=failed,
	)
