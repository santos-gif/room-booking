"""The `date` query parameter of the availability route, checked where hostile input enters."""
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Query

from app.api.v1.appointment.exceptions import AppointmentValidationException
from app.api.v1.appointment.slots import MAX_ADVANCE
from app.api.v1.appointment.types import JAKARTA_TZ


def _valid_booking_date(booking_date: date = Query(alias="date")) -> date:
	# Years 1 or 9999 would overflow the database's date arithmetic and answer with a 500.
	today = datetime.now(JAKARTA_TZ).date()
	if not today - timedelta(days=1) <= booking_date <= today + MAX_ADVANCE + timedelta(days=1):
		raise AppointmentValidationException("Choose a date within the next 90 days.")
	return booking_date


BookingDate = Annotated[date, Depends(_valid_booking_date)]
