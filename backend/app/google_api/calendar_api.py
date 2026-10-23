import logging
from typing import Any

import google_auth_httplib2
import httplib2
from fastapi import Response
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import TypeAdapter
from supabase import Client

from app.config import settings
from app.google_api.credentials import calendar_credentials
from app.google_api.exceptions import (
	GoogleCalendarAccessException,
	GoogleCalendarOperationException,
	GoogleConfigurationException,
)
from app.google_api.types import GoogleCalendarEvent

logger = logging.getLogger(__name__)
CALENDAR_HTTP_TIMEOUT_SEC = 10


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


def calendar_service(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> Any:
	credentials = calendar_credentials(
		supabase, user_id, access_token, expires_at, response
	)
	# Google's default is 60 s per call, longer than a serverless request can afford.
	http = google_auth_httplib2.AuthorizedHttp(
		credentials, http=httplib2.Http(timeout=CALENDAR_HTTP_TIMEOUT_SEC)
	)
	return build("calendar", "v3", http=http, cache_discovery=False)


def _no_write_access(error: HttpError) -> bool:
	"""404 (calendar unknown to this account) or a 403 that is not just Google's rate limit."""
	if error.resp.status == 404:
		return True
	text = str(error.content).lower()
	return error.resp.status == 403 and "ratelimit" not in text and "quota" not in text


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
	service = calendar_service(supabase, user_id, access_token, expires_at, response)
	body = {**event_body, "id": event_id}
	# The caller-chosen ID makes insert idempotent: after a dropped reply, get() tells us
	# whether Google processed it. One retry only; a second unknown outcome is a failure.
	for _ in range(2):
		try:
			return service.events().insert(calendarId=calendar_id, body=body).execute()
		except HttpError as error:
			# 409 = this ID already exists (an earlier attempt landed); 5xx = gateway/timeout.
			if _no_write_access(error):
				raise GoogleCalendarAccessException() from error
			if error.resp.status != 409 and error.resp.status < 500:
				raise GoogleCalendarOperationException() from error
		except GoogleAuthError as error:
			raise GoogleCalendarOperationException() from error
		except (httplib2.HttpLib2Error, OSError):
			pass
		try:
			existing = service.events().get(
				calendarId=calendar_id,
				eventId=event_id,
			).execute()
		except HttpError as error:
			if error.resp.status != 404:
				raise GoogleCalendarOperationException() from error
			logger.warning("Calendar event %s was not created; retrying.", event_id)
			continue
		except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
			raise GoogleCalendarOperationException() from error
		logger.info("Calendar event %s exists despite the failed response.", event_id)
		return existing
	raise GoogleCalendarOperationException()


def get_calendar_events(
	supabase: Client,
	user_id: str,
	access_token: str | None,
	expires_at: int | None,
	response: Response,
) -> list[GoogleCalendarEvent]:
	service = calendar_service(
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
