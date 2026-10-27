import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from app.google_api.credentials import CALENDAR_SCOPES, calendar_credentials
from app.google_api.exceptions import GoogleConfigurationException


def _service_account_json() -> str:
	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	pem = key.private_bytes(
		serialization.Encoding.PEM,
		serialization.PrivateFormat.PKCS8,
		serialization.NoEncryption(),
	).decode()
	return json.dumps({
		"type": "service_account",
		"client_email": "rooms@example-project.iam.gserviceaccount.com",
		"private_key": pem,
		"token_uri": "https://oauth2.googleapis.com/token",
	})


class ServiceAccountCredentialsTests(unittest.TestCase):
	def setUp(self) -> None:
		calendar_credentials.cache_clear()
		self.addCleanup(calendar_credentials.cache_clear)

	def test_the_configured_key_becomes_calendar_only_credentials(self) -> None:
		with patch.object(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", _service_account_json()):
			credentials = calendar_credentials()
			self.assertIs(calendar_credentials(), credentials)  # cached for the warm instance
		self.assertEqual(credentials.service_account_email, "rooms@example-project.iam.gserviceaccount.com")
		self.assertEqual(list(credentials.scopes), CALENDAR_SCOPES)

	def test_an_unusable_key_is_a_configuration_error_that_never_echoes_it(self) -> None:
		for value in ("", "not json", '{"type": "service_account", "private_key": "SECRET-LOOKING-VALUE"}'):
			with self.subTest(value=value[:12]), patch.object(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", value):
				with self.assertRaises(GoogleConfigurationException) as caught:
					calendar_credentials()
				self.assertNotIn("SECRET-LOOKING-VALUE", str(caught.exception.detail))


if __name__ == "__main__":
	unittest.main()
