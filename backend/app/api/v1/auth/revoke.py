"""Really ending a Supabase session. Clearing cookies alone leaves a copied refresh token valid."""
import logging

from app.database import create_supabase_client

logger = logging.getLogger(__name__)


def revoke_session(access_token: str | None, refresh_token: str | None) -> bool:
	"""Revokes every session of the user behind these cookies. True if Supabase confirmed it.

	supabase-py's sign_out() only acts on a session held in the client's memory, which a client built
	from a bare Authorization header does not have, so it silently does nothing. The reliable way is the
	admin endpoint with a valid access token; the stored one may be expired by logout time, so a refresh
	token is first traded for a fresh one (which also invalidates the old refresh token).
	"""
	client = create_supabase_client()
	token = access_token
	try:
		if refresh_token:
			try:
				token = client.auth.refresh_session(refresh_token).session.access_token  # type: ignore[union-attr]
			except Exception:  # noqa: BLE001 - e.g. already rotated by another tab: the access token may still work
				logger.warning("Could not renew the session before revoking it.", exc_info=True)
		if not token:
			return False
		client.auth.admin.sign_out(token, "global")
		return True
	except Exception:  # noqa: BLE001 - logout must still clear the cookies
		logger.warning("Supabase session revocation failed during logout.", exc_info=True)
		return False
