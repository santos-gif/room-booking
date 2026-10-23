from contextlib import asynccontextmanager
import logging
import secrets
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.api_router import api_router
from app.cookies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, set_csrf_cookie
from app.config import (
	settings,
	validate_integration_configuration,
	validate_security_secrets,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
	validate_integration_configuration()
	validate_security_secrets()
	yield


# No public API docs: the schema would hand an attacker a map of every route.
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

cors_origins = [
	origin.strip()
	for origin in settings.CORS_ORIGINS.split(",")
	if origin.strip()
]

if "*" in cors_origins:
	# With credentials a wildcard would let any website call the API as the signed-in student.
	raise RuntimeError("CORS_ORIGINS must list explicit origins, not *.")

app.add_middleware(
	CORSMiddleware,
	allow_origins=cors_origins,
	allow_credentials=True,
	allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
	allow_headers=["Content-Type", "X-CSRF-Token", "X-Retry-Attempt"],
	expose_headers=["X-Reconnect-Google"],
)


@app.exception_handler(APIError)
async def handle_database_error(_request: Request, _error: APIError) -> JSONResponse:
	logger.exception("Unhandled Supabase request failure.")
	return JSONResponse(
		status_code=500,
		content={"detail": "A database operation failed. Please try again."},
	)

@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
	logger.exception("Unhandled server error.")
	# No stack trace or internals in the body. CORS: Starlette serves this from
	# ServerErrorMiddleware, outside CORSMiddleware, so the browser may not see CORS headers.
	return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.middleware("http")
async def check_csrf_cookie(
	request: Request,
	call_next: RequestResponseEndpoint,
) -> Response:
	# QUICK FIX: Bypass authentication/OAuth callback endpoints entirely
	if request.url.path == "/api/v1/google-auth/oauth2callback":
		return await call_next(request)

	if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
		response = await call_next(request)
		if request.cookies.get(ACCESS_COOKIE) and not request.cookies.get(CSRF_COOKIE):
			set_csrf_cookie(response)
		return response
	if not request.url.path.startswith("/api/v1/"):
		return await call_next(request)
	if not request.cookies.get(ACCESS_COOKIE) and not request.cookies.get(REFRESH_COOKIE):
		return await call_next(request)
	cookie_token = request.cookies.get(CSRF_COOKIE)
	header_token = request.headers.get("x-csrf-token")
	if (
		not cookie_token
		or not header_token
		# Bytes: compare_digest raises TypeError (a 500) on a non-ASCII str.
		or not secrets.compare_digest(cookie_token.encode(), header_token.encode())
	):
		return JSONResponse(
			status_code=403,
			content={"detail": "CSRF validation failed. Refresh and try again."},
		)
	return await call_next(request)


app.include_router(api_router)


@app.middleware("http")
async def add_api_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
	response = await call_next(request)
	# Per-student answers must never sit in a shared cache.
	response.headers["Cache-Control"] = "no-store"
	response.headers["X-Content-Type-Options"] = "nosniff"
	return response
