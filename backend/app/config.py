

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file="env.local",
		case_sensitive=True,
		extra="ignore"
	)
	CORS_ORIGINS:list[str] = ["http://localhost:4200"]

settings = Settings()
