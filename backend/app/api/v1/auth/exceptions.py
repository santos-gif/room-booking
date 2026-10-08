from fastapi import HTTPException, status


class CredentialsException(HTTPException):
	def __init__(self):
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Could not validate credentials",
			headers={"WWW-Authenticate": "Bearer: access-token"}
		)

class ExpiredAccessToken(HTTPException):
	def __init__(self):
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Access Token has expired",
			headers={"WWW-Authenticate": "Bearer: access-token"}
		)

class ExpiredRefreshToken(HTTPException):
	def __init__(self):
		super().__init__(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Refresh Token has expired",
			headers={"WWW-Authenticate": "Bearer: refresh-token"}
		)

class UserNotFoundException(HTTPException):
	def __init__(self):
		super().__init__(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="User Not Found"
		)
