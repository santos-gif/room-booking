

from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=Path(__file__).resolve().parents[1] / ".env.local",
		env_file_encoding="utf-8",
		case_sensitive=True,
		extra="ignore"
	)
	CORS_ORIGINS: str = "http://localhost:4200"
	FRONTEND_URL: str = "http://localhost:4200"
	COOKIE_SECURE: bool = True
	COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

	GOOGLE_CLIENT_ID: str = ""
	GOOGLE_CLIENT_SECRET: str = ""
	GOOGLE_REDIRECT_URI: str = ""
	GOOGLE_CALENDAR_ROOM_1_ID: str = ""
	GOOGLE_CALENDAR_ROOM_2_ID: str = ""
	GOOGLE_CALENDAR_ID: str = ""
	GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""
	CRON_SECRET: str = ""

	ALGORITHM: str = "HS256"
	SECRET_ACCESS_TOKEN_JWT_KEY: str = ""
	SECRET_REFRESH_TOKEN_JWT_KEY: str = ""

	SUPABASE_URL: str = ""
	SUPABASE_KEY: str = ""


settings = Settings()


def validate_security_secrets() -> None:
	secrets_to_check = {
		"SECRET_ACCESS_TOKEN_JWT_KEY": settings.SECRET_ACCESS_TOKEN_JWT_KEY,
		"SECRET_REFRESH_TOKEN_JWT_KEY": settings.SECRET_REFRESH_TOKEN_JWT_KEY,
		"CRON_SECRET": settings.CRON_SECRET,
	}
	invalid = [
		name
		for name, value in secrets_to_check.items()
		if len(value) < 32 or value != value.strip()
	]
	if invalid:
		names = ", ".join(invalid)
		raise RuntimeError(
			f"Security secrets must be configured with at least 32 characters: {names}"
		)
	if settings.SECRET_ACCESS_TOKEN_JWT_KEY == settings.SECRET_REFRESH_TOKEN_JWT_KEY:
		raise RuntimeError(
			"SECRET_ACCESS_TOKEN_JWT_KEY and SECRET_REFRESH_TOKEN_JWT_KEY "
			"must be different."
		)


def validate_integration_configuration() -> None:
	required_settings = {
		"SUPABASE_URL": settings.SUPABASE_URL,
		"SUPABASE_KEY": settings.SUPABASE_KEY,
		"GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
		"GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
		"GOOGLE_REDIRECT_URI": settings.GOOGLE_REDIRECT_URI,
		"GOOGLE_CALENDAR_ROOM_1_ID": settings.GOOGLE_CALENDAR_ROOM_1_ID,
		"GOOGLE_CALENDAR_ROOM_2_ID": settings.GOOGLE_CALENDAR_ROOM_2_ID,
		"GOOGLE_TOKEN_ENCRYPTION_KEY": settings.GOOGLE_TOKEN_ENCRYPTION_KEY,
	}
	missing = [name for name, value in required_settings.items() if not value.strip()]
	if missing:
		names = ", ".join(missing)
		legacy_calendar_id = (
			" GOOGLE_CALENDAR_ID is not used; configure "
			"GOOGLE_CALENDAR_ROOM_1_ID and GOOGLE_CALENDAR_ROOM_2_ID."
			if settings.GOOGLE_CALENDAR_ID
			else ""
		)
		raise RuntimeError(
			f"Missing required integration configuration: {names}.{legacy_calendar_id}"
		)
	try:
		Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode("ascii"))
	except (UnicodeEncodeError, ValueError) as error:
		raise RuntimeError(
			"GOOGLE_TOKEN_ENCRYPTION_KEY must be a valid Fernet key."
		) from error
