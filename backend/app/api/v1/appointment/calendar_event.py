"""What a booking looks like on the shared room calendar: its title and its Google event body."""
from datetime import datetime

from app.api.v1.appointment.types import JAKARTA_TZ
from app.api.v1.auth.types import AuthenticatedUser

MAX_NAME_LENGTH = 60


def build_calendar_event(
	appointment_id: str,
	room_number: int,
	start_time: datetime,
	end_time: datetime,
	name: str | None = None,
	nim: int | None = None,
) -> dict[str, object]:
	# Without a name and NIM (reconcile rows do not carry them) fall back to the room only.
	title = f"Discussion Room {room_number}"
	if name and nim is not None:
		title = f"{title}-{name} ({nim})"
	return {
		"summary": title,
		"description": f"Room booking appointment ID: {appointment_id}",
		"start": {"dateTime": start_time.isoformat(), "timeZone": JAKARTA_TZ.key},
		"end": {"dateTime": end_time.isoformat(), "timeZone": JAKARTA_TZ.key},
	}


def booker_name(user: AuthenticatedUser) -> str:
	"""Name for the event title: one short line, no control characters (it is shown on the room calendar)."""
	one_line = " ".join((user.name or "").split())
	name = "".join(c for c in one_line if c.isprintable())[:MAX_NAME_LENGTH].strip()
	return name or user.email.partition("@")[0]
