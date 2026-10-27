from typing import Any

import httplib2
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError

from app.google_api.calendar_api import calendar_service
from app.google_api.exceptions import GoogleCalendarOperationException


def delete_calendar_event(calendar_id: str, event_id: str) -> None:
	try:
		calendar_service().events().delete(
			calendarId=calendar_id,
			eventId=event_id,
		).execute()
	except HttpError as error:
		if error.resp.status not in (404, 410):
			raise GoogleCalendarOperationException() from error
	except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def calendar_is_reachable(calendar_id: str) -> bool:
	"""True if the service account can read the room calendar; False if it is unknown or no longer shared."""
	try:
		# events.list, not calendars.get: the narrow calendar.events scope forbids calendars.get (checked live).
		calendar_service().events().list(calendarId=calendar_id, maxResults=1).execute()
		return True
	except HttpError as error:
		if error.resp.status in (403, 404, 410):
			return False
		raise GoogleCalendarOperationException() from error
	except (GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def update_calendar_event(
	calendar_id: str,
	event_id: str,
	event_body: dict[str, Any],
) -> dict[str, Any]:
	try:
		result: dict[str, Any] = calendar_service().events().update(
			calendarId=calendar_id,
			eventId=event_id,
			body={**event_body, "id": event_id},
		).execute()
		return result
	except (HttpError, GoogleAuthError, httplib2.HttpLib2Error, OSError) as error:
		raise GoogleCalendarOperationException() from error


def get_calendar_event(calendar_id: str, event_id: str) -> dict[str, Any] | None:
	try:
		result: dict[str, Any] = calendar_service().events().get(
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
