from fastapi import HTTPException, status


class AppointmentStorageException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Supabase returned an invalid appointment record.",
		)


class AppointmentValidationException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
			detail=detail,
		)


class AppointmentConflictException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_409_CONFLICT,
			detail="That time slot was just booked. Please choose another time.",
		)


class DailyBookingLimitException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_409_CONFLICT,
			detail="You can have at most three upcoming appointments.",
		)


class AppointmentNotFoundException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Appointment not found.",
		)


class CalendarSyncException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="The booking could not be synchronized with Google Calendar.",
		)


class ProfileIncompleteException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Complete your profile (NIM) before booking.",
		)
