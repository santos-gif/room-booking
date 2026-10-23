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


# Tells the frontend this 401 means "the Google connection is unusable", not "the app session ended".
RECONNECT_HEADER = "X-Reconnect-Google"


class GoogleAuthorizationException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=detail,
			headers={RECONNECT_HEADER: "1"},
		)


class GoogleCredentialException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail=detail,
		)


class GoogleUnavailableException(GoogleCredentialException):
	"""Google did not answer the token refresh in time; the stored token is untouched."""

	def __init__(self) -> None:
		super().__init__("Google is not responding. Please try again in a moment.")
		self.status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class GoogleIdentityException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=detail,
		)


class GoogleRefreshTokenException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=detail,
			headers={RECONNECT_HEADER: "1"},
		)


class GoogleRefreshConsentException(HTTPException):
	def __init__(self) -> None:
		super().__init__(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=(
				"Google did not return a refresh token. Revoke existing access and "
				"reconnect to grant offline access."
			),
		)


class GoogleTokenStorageException(HTTPException):
	def __init__(self, detail: str) -> None:
		super().__init__(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
	"""The signed-in Google account may not write to the room calendar (not shared with it)."""
