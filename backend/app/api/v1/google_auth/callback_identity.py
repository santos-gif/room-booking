"""Who may sign in: the checks on the Google identity, made before any session exists."""
from app.google_api.types import GoogleIdentity

ALLOWED_DOMAINS = {"student.pradita.ac.id", "pradita.ac.id"}


class SignInRefused(Exception):
	"""The sign-in is refused. `code` is the fixed error code the login page turns into a message."""

	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.code = code


def is_allowed_email(email: str) -> bool:
	local_part, separator, domain = email.rpartition("@")
	# ASCII only and lower(): the same comparison the database makes (casefold would also fold odd letters).
	return bool(email.isascii() and separator and local_part and domain.lower() in ALLOWED_DOMAINS)


def verified_university_email(identity: GoogleIdentity) -> str:
	"""The lower-cased email of an identity that may sign in; raises SignInRefused for anyone else."""
	if not identity.sub or not identity.email or not identity.email_verified:
		raise SignInRefused("verified_email_required")
	email = identity.email.strip().lower()
	# A verified address alone is not enough: Google must also vouch that the account belongs to a Pradita
	# Workspace (hd is the tenant's primary domain, so it need not equal the email's domain).
	if not is_allowed_email(email) or (identity.hd or "").lower() not in ALLOWED_DOMAINS:
		raise SignInRefused("university_email_required")
	return email
