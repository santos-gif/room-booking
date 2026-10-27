from fastapi import HTTPException, status


class GoogleOAuthStateException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Invalid Google OAuth state. Please start the connection again.",
		)


class GoogleOAuthRequestException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=detail,
		)


class GoogleCredentialException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail=detail,
		)


class GoogleIdentityException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=detail,
		)


class GoogleConfigurationException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=detail,
		)


class GoogleCalendarOperationException(Exception):
	pass


class GoogleCalendarAccessException(GoogleCalendarOperationException):
	"""The service account may not write to the room calendar (not shared with it)."""
