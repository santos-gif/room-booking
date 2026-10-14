from datetime import datetime, timedelta, timezone
from typing import Any

import httplib2
from fastapi import Response
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import TypeAdapter
from supabase import Client

from app.api.v1.google_auth.exceptions import (
	GoogleAuthorizationException,
	GoogleCalendarOperationException,
	GoogleConfigurationException,
	GoogleCredentialException,
	GoogleRefreshTokenException,
)
from app.api.v1.google_auth.helper import decrypt_refresh_token
from app.api.v1.google_auth.oauth_flow import SCOPES
from app.api.v1.google_auth.types import GoogleCalendarEvent
from app.config import settings
from app.models.google_refresh_token import GoogleRefreshTokenRecord

GOOGLE_ACCESS_COOKIE = "google_access_token"
GOOGLE_ACCESS_EXPIRY_COOKIE = "google_access_token_expires_at"


def set_google_access_cookie(
	response: Response,
	access_token: str,
	expires_at: datetime | None,
) -> None:
	now = datetime.now(timezone.utc)
	if expires_at is None:
		expires_at = now + timedelta(hours=1)
	elif expires_at.tzinfo is None:
		expires_at = expires_at.replace(tzinfo=timezone.utc)
	else:
		expires_at = expires_at.astimezone(timezone.utc)
	max_age = max(0, int((expires_at - now).total_seconds()))
	cookie_options = {
		"httponly": True,
		"secure": settings.COOKIE_SECURE,
		"samesite": settings.COOKIE_SAMESITE,
		"path": "/",
		"max_age": max_age,
	}
	response.set_cookie(key=GOOGLE_ACCESS_COOKIE, value=access_token, **cookie_options)
	response.set_cookie(
		key=GOOGLE_ACCESS_EXPIRY_COOKIE,
		value=str(int(expires_at.timestamp())),
		**cookie_options,
	)


def _calendar_credentials(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> Credentials:
	result = (
		supabase.rpc(
			"get_google_refresh_token",
			{
				"requested_profile_id": user_id,
				"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET,
			},
		)
		.execute()
	)
	records = TypeAdapter(list[GoogleRefreshTokenRecord]).validate_python(result.data)
	if not records or not records[0].is_valid:
		raise GoogleRefreshTokenException(
			"No valid Google Calendar connection is available for this user."
		)
	expiry = (
		datetime.fromtimestamp(expires_at, timezone.utc).replace(tzinfo=None)
		if expires_at is not None
		else None
	)
	credentials = Credentials(
		token=access_token,
		refresh_token=decrypt_refresh_token(records[0].refresh_token),
		token_uri="https://oauth2.googleapis.com/token",
		client_id=settings.GOOGLE_CLIENT_ID,
		client_secret=settings.GOOGLE_CLIENT_SECRET,
		scopes=SCOPES,
		expiry=expiry,
	)
	if not credentials.token or credentials.expired:
		try:
			credentials.refresh(GoogleAuthRequest())
		except RefreshError as error:
			supabase.rpc(
				"invalidate_google_refresh_token",
				{
					"requested_profile_id": user_id,
					"backend_secret": settings.SUPABASE_BACKEND_RPC_SECRET,
				},
			).execute()
			raise GoogleAuthorizationException(
				"Google authorization expired or was revoked. Connect Google Calendar again."
			) from error
		if not credentials.token:
			raise GoogleCredentialException("Google did not return an access token.")
		set_google_access_cookie(response, credentials.token, credentials.expiry)
	return credentials


def room_calendar_id(room_number: int) -> str:
	calendar_ids = {
		1: settings.GOOGLE_CALENDAR_ROOM_1_ID,
		2: settings.GOOGLE_CALENDAR_ROOM_2_ID,
	}
	calendar_id = calendar_ids.get(room_number)
	if not calendar_id:
		raise GoogleConfigurationException(
			f"Google Calendar is not configured for room {room_number}."
		)
	return calendar_id


def _calendar_service(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> Any:
	credentials = _calendar_credentials(
		supabase, user_id, access_token, expires_at, response
	)
	return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def create_calendar_event(
	supabase: Client,
	user_id: str,
	calendar_id: str,
	event_id: str,
	event_body: dict[str, Any],
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> dict[str, Any]:
	try:
		service = _calendar_service(
			supabase, user_id, access_token, expires_at, response
		)
		return service.events().get(
			calendarId=calendar_id,
			eventId=event_id,
		).execute()
	except HttpError as error:
		if error.resp.status != 404:
			raise GoogleCalendarOperationException() from error
		try:
			return service.events().insert(
				calendarId=calendar_id,
				body={**event_body, "id": event_id},
			).execute()
		except (HttpError, GoogleAuthError, httplib2.HttpLib2Error, OSError) as insert_error:
			raise GoogleCalendarOperationException() from insert_error
	except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def delete_calendar_event(
	supabase: Client,
	user_id: str,
	calendar_id: str,
	event_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> None:
	try:
		service = _calendar_service(
			supabase, user_id, access_token, expires_at, response
		)
		service.events().delete(
			calendarId=calendar_id,
			eventId=event_id,
		).execute()
	except HttpError as error:
		if error.resp.status not in (404, 410):
			raise GoogleCalendarOperationException() from error
	except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def update_calendar_event(
	supabase: Client,
	user_id: str,
	calendar_id: str,
	event_id: str,
	event_body: dict[str, Any],
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> dict[str, Any]:
	try:
		service = _calendar_service(
			supabase, user_id, access_token, expires_at, response
		)
		result: dict[str, Any] = service.events().update(
			calendarId=calendar_id,
			eventId=event_id,
			body={**event_body, "id": event_id},
		).execute()
		return result
	except (HttpError, GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def get_calendar_event(
	supabase: Client,
	user_id: str,
	calendar_id: str,
	event_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> dict[str, Any] | None:
	try:
		service = _calendar_service(
			supabase, user_id, access_token, expires_at, response
		)
		result: dict[str, Any] = service.events().get(
			calendarId=calendar_id,
			eventId=event_id,
		).execute()
		return result
	except HttpError as error:
		if error.resp.status in (404, 410):
			return None
		raise GoogleCalendarOperationException() from error
	except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def get_calendar_events(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> list[GoogleCalendarEvent]:
	service = _calendar_service(
		supabase, user_id, access_token, expires_at, response
	)
	events: list[dict[str, Any]] = []
	for room_number in (1, 2):
		result: dict[str, Any] = service.events().list(
			calendarId=room_calendar_id(room_number),
			maxResults=250,
		).execute()
		events.extend(result.get("items", []))
	return TypeAdapter(list[GoogleCalendarEvent]).validate_python(events)
