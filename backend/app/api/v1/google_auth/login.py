import secrets

from fastapi.responses import RedirectResponse

from app.cookies import set_oauth_cookies
from app.google_api.oauth import create_flow


def create_google_login_response() -> RedirectResponse:
	code_verifier = secrets.token_urlsafe(64)
	state = secrets.token_urlsafe(32)
	flow = create_flow(state, code_verifier)
	authorization_url, _ = flow.authorization_url(
		access_type="offline",
		prompt="select_account consent",
		include_granted_scopes="true",
		code_challenge_method="S256",
	)
	response = RedirectResponse(authorization_url, status_code=302)
	set_oauth_cookies(response, state, code_verifier)
	return response
