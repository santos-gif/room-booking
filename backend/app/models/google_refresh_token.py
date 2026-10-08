from pydantic import BaseModel


class GoogleRefreshTokenRecord(BaseModel):
	refresh_token: str
	is_valid: bool
