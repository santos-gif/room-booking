from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AppointmentStatus = Literal["pending", "confirmed", "cancelled"]
CalendarSyncStatus = Literal["pending", "synced", "failed", "legacy"]


class AppointmentRecord(BaseModel):
	model_config = ConfigDict(extra="ignore")

	id: str
	booker_id: str
	room_number: int
	start_time: datetime
	end_time: datetime
	status: AppointmentStatus
	sync_status: CalendarSyncStatus
	google_calendar_id: str | None = None
	google_event_id: str | None = None
	replaces_appointment_id: str | None = None
