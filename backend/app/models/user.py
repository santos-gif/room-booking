from pydantic import BaseModel, ConfigDict


class UserRecord(BaseModel):
	model_config = ConfigDict(extra="ignore")

	id: str
	email: str
	name: str | None = None
	nim: int | None = None
	major: str | None = None
	role: str = "student"
