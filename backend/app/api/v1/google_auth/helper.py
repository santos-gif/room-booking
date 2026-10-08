from cryptography.fernet import Fernet, InvalidToken

from app.api.v1.google_auth.exceptions import (
	GoogleConfigurationException,
	GoogleTokenStorageException,
)
from app.config import settings


def _fernet() -> Fernet:
	if not settings.GOOGLE_TOKEN_ENCRYPTION_KEY:
		raise GoogleConfigurationException(
			"GOOGLE_TOKEN_ENCRYPTION_KEY must be configured to store Google refresh tokens."
		)
	try:
		return Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode("ascii"))
	except (TypeError, UnicodeEncodeError, ValueError) as error:
		raise GoogleConfigurationException(
			"GOOGLE_TOKEN_ENCRYPTION_KEY must be a valid Fernet key."
		) from error


def encrypt_refresh_token(refresh_token: str) -> str:
	return _fernet().encrypt(refresh_token.encode("utf-8")).decode("ascii")


def decrypt_refresh_token(encrypted_refresh_token: str) -> str:
	try:
		return _fernet().decrypt(encrypted_refresh_token.encode("ascii")).decode("utf-8")
	except (InvalidToken, UnicodeEncodeError) as error:
		raise GoogleTokenStorageException(
			"Could not decrypt the stored Google refresh token. Check the encryption key."
		) from error
