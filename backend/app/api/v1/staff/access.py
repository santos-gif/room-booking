"""Who may use the staff routes, and how the staff functions' database errors read to the client."""
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException
from postgrest.exceptions import APIError

from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser


def require_staff(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
	# Every staff function checks the role again inside the database; this keeps the answer a clean 403.
	if current_user.role != "staff":
		raise HTTPException(status_code=403, detail="Staff only.")
	return current_user


@contextmanager
def staff_db_errors() -> Iterator[None]:
	"""Turns the errors the staff functions raise on purpose into 4xx answers instead of a 500."""
	try:
		yield
	except APIError as error:
		code = error.code or ""
		if code == "42501":
			raise HTTPException(status_code=403, detail="Staff only.") from error
		if code == "22023":
			raise HTTPException(status_code=422, detail="Check the room, dates and reason.") from error
		if code == "P0002":
			raise HTTPException(status_code=404, detail="Closure not found.") from error
		if code == "23514":
			closed = "closed" in (error.message or "").lower()
			raise HTTPException(
				status_code=409,
				detail="The room is closed on that date."
				if closed
				else "Choose a weekday slot starting between 08:00 and 16:00 WIB.",
			) from error
		if code == "23P01":
			raise HTTPException(status_code=409, detail="That slot was just taken. Try again.") from error
		raise
