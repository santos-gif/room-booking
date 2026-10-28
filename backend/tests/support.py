"""Shared builders for the backend test modules."""
from datetime import date, datetime, time, timedelta, timezone


from app.api.v1.appointment.types import JAKARTA_TZ
from app.api.v1.auth.types import AuthenticatedUser


def student_user(user_id: str = "user-id") -> AuthenticatedUser:
	"""Fake a signed-in student with the given profile id."""
	return AuthenticatedUser(
		id=user_id,
		email="student@student.pradita.ac.id",
		name="Santos Mahasiswa",
		nim=2510101051,
	)


def next_weekday_start(hour: int) -> datetime:
	"""Return a Jakarta-time slot start on the next weekday after today."""
	day = date.today() + timedelta(days=1)
	while day.weekday() > 4:
		day += timedelta(days=1)
	return datetime.combine(day, time(hour), tzinfo=JAKARTA_TZ)


def pending_record(appointment_id: str, start: datetime) -> dict[str, object]:
	"""Fake the pending one-hour appointment row returned by the insert."""
	return {
		"id": appointment_id,
		"booker_id": "user-id",
		"room_number": 1,
		"start_time": start.astimezone(timezone.utc).isoformat(),
		"end_time": (start + timedelta(hours=1))
		.astimezone(timezone.utc)
		.isoformat(),
		"status": "pending",
		"sync_status": "pending",
	}


def staff_user() -> AuthenticatedUser:
	"""Fake a signed-in staff member."""
	return student_user("staff-id").model_copy(update={"role": "staff", "name": "Bu Dosen"})


def cancelled_row(n: int) -> dict[str, object]:
	"""A booking staff cancelled, still waiting for its Google event to be deleted."""
	return {"id": f"old{n}", "status": "cancelled", "google_calendar_id": "cal", "google_event_id": f"ev{n}"}

