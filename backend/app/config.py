

import json
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _backend_root() -> Path:
	return Path(__file__).resolve().parents[1]


def _load_google_client_secret_file() -> dict[str, Any]:
	backend_root = _backend_root()
	for filename in ("google_client_secret", "client_secret.json"):
		path = backend_root / filename
		if not path.exists():
			continue
		try:
			payload = json.loads(path.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue
		if isinstance(payload, dict):
			if isinstance(payload.get("web"), dict):
				return payload["web"]
			return payload
	return {}


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=[
			_backend_root() / ".env.dev",
			_backend_root() / ".env.local",
		],
		env_file_encoding="utf-8",
		case_sensitive=True,
		extra="ignore",
	)
	CORS_ORIGINS: str = "http://localhost:3000"
	FRONTEND_URL: str = "http://localhost:3000"
	COOKIE_SECURE: bool = True
	COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

	GOOGLE_CLIENT_ID: str = ""
	GOOGLE_CLIENT_SECRET: str = ""
	GOOGLE_REDIRECT_URI: str = ""
	GOOGLE_CALENDAR_ROOM_1_ID: str = ""
	GOOGLE_CALENDAR_ROOM_2_ID: str = ""
	GOOGLE_CALENDAR_ID: str = ""
	GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
	CRON_SECRET: str = ""
	SUPABASE_BACKEND_RPC_SECRET: str = ""

	SUPABASE_URL: str = ""
	SUPABASE_KEY: str = ""


settings = Settings()
secret_file_values = _load_google_client_secret_file()
if not settings.GOOGLE_CLIENT_ID and isinstance(secret_file_values.get("client_id"), str):
	settings.GOOGLE_CLIENT_ID = secret_file_values["client_id"]
if not settings.GOOGLE_CLIENT_SECRET and isinstance(secret_file_values.get("client_secret"), str):
	settings.GOOGLE_CLIENT_SECRET = secret_file_values["client_secret"]
if not settings.GOOGLE_REDIRECT_URI:
	redirect_uris = secret_file_values.get("redirect_uris")
	if isinstance(redirect_uris, list):
		for candidate in redirect_uris:
			if isinstance(candidate, str):
				settings.GOOGLE_REDIRECT_URI = candidate
				break


def validate_security_secrets() -> None:
	secrets_to_check = {
		"CRON_SECRET": settings.CRON_SECRET,
		"SUPABASE_BACKEND_RPC_SECRET": settings.SUPABASE_BACKEND_RPC_SECRET,
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
	if settings.CRON_SECRET == settings.SUPABASE_BACKEND_RPC_SECRET:
		raise RuntimeError(
			"CRON_SECRET and SUPABASE_BACKEND_RPC_SECRET must be different."
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
		"GOOGLE_SERVICE_ACCOUNT_JSON": settings.GOOGLE_SERVICE_ACCOUNT_JSON,
		"SUPABASE_BACKEND_RPC_SECRET": settings.SUPABASE_BACKEND_RPC_SECRET,
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
	from app.google_api.credentials import calendar_credentials  # here: credentials.py imports this module

	calendar_credentials()  # fails at startup, not on the first booking, if the key is unusable
