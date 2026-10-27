import json
from functools import lru_cache

from google.oauth2 import service_account

from app.config import settings
from app.google_api.exceptions import GoogleConfigurationException

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@lru_cache(maxsize=1)
def calendar_credentials() -> service_account.Credentials:
	"""The project's own Google identity, shared by every booking; students never hand over Calendar access.

	Cached so a warm instance reuses its access token; google-auth renews it on demand inside each call.
	"""
	try:
		info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
		return service_account.Credentials.from_service_account_info(info, scopes=CALENDAR_SCOPES)
	except (ValueError, TypeError) as error:
		# Never echo the value: it is the private key.
		raise GoogleConfigurationException("GOOGLE_SERVICE_ACCOUNT_JSON is not a valid service account key.") from error
