from contextlib import asynccontextmanager
import logging
import secrets
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.api_router import api_router
from app.config import (
	settings,
	validate_integration_configuration,
	validate_security_secrets,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
	validate_integration_configuration()
	validate_security_secrets()
	yield


app = FastAPI(lifespan=lifespan)

cors_origins = [
	origin.strip()
	for origin in settings.CORS_ORIGINS.split(",")
	if origin.strip()
]

app.add_middleware(
	CORSMiddleware,
	allow_origins=cors_origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
	)


@app.exception_handler(APIError)
async def handle_database_error(_request: Request, error: APIError) -> JSONResponse:
	logger.exception("Unhandled Supabase request failure.")
	return JSONResponse(
		status_code=500,
		content={"detail": "A database operation failed. Please try again."},
	)


@app.middleware("http")
async def check_csrf_cookie(
	request: Request,
	call_next: RequestResponseEndpoint,
) -> Response:
	if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
		response = await call_next(request)
		if request.cookies.get("access_token") and not request.cookies.get("csrf_token"):
			response.set_cookie(
				key="csrf_token",
				value=secrets.token_urlsafe(32),
				max_age=30 * 24 * 60 * 60,
				httponly=False,
				secure=settings.COOKIE_SECURE,
				samesite=settings.COOKIE_SAMESITE,
				path="/",
			)
		return response
	if not request.url.path.startswith("/api/v1/"):
		return await call_next(request)
	if not request.cookies.get("access_token") and not request.cookies.get(
		"refresh_token"
	):
		return await call_next(request)
	cookie_token = request.cookies.get("csrf_token")
	header_token = request.headers.get("x-csrf-token")
	if (
		not cookie_token
		or not header_token
		or not secrets.compare_digest(cookie_token, header_token)
	):
		return JSONResponse(
			status_code=403,
			content={"detail": "CSRF validation failed. Refresh and try again."},
		)
	return await call_next(request)


app.include_router(api_router)
