from typing import Any

import httplib2
from fastapi import Response
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from supabase import Client

from app.google_api.calendar_api import calendar_service
from app.google_api.exceptions import GoogleCalendarOperationException


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
		service = calendar_service(
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
		service = calendar_service(
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
		service = calendar_service(
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
