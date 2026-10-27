from pydantic import BaseModel


class GoogleIdentity(BaseModel):
	sub: str
	email: str | None = None
	email_verified: bool = False
	name: str | None = None
	# Workspace domain Google vouches for; absent for ordinary Google accounts.
	hd: str | None = None

__all__ = ["GoogleIdentity"]
