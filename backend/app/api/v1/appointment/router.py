from datetime import date
import secrets
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.v1.appointment.helper import (
	cancel_appointment,
	create_appointment,
	get_availability,
	list_appointments,
	reconcile_appointments,
	reschedule_appointment,
)
from app.api.v1.appointment.types import (
	AppointmentPayload,
	AppointmentResponse,
	AvailabilityResponse,
	ReconciliationResponse,
	ReschedulePayload,
)
from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.google_auth.calendar_helper import (
	GOOGLE_ACCESS_COOKIE,
	GOOGLE_ACCESS_EXPIRY_COOKIE,
)
from app.database import PublicSupabaseClient, SupabaseClient
from app.config import settings

router = APIRouter(prefix="/appointments")


@router.get("/", response_model=list[AppointmentResponse])
async def get_appointments(
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[AppointmentResponse]:
	return await run_in_threadpool(list_appointments, supabase, current_user)


@router.get("/availability", response_model=AvailabilityResponse)
async def get_available_slots(
	supabase: SupabaseClient,
	booking_date: date = Query(alias="date"),
	room_number: int = Query(ge=1, le=2),
	exclude_appointment_id: UUID | None = Query(default=None),
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> AvailabilityResponse:
	return await run_in_threadpool(
		get_availability,
		supabase,
		booking_date,
		room_number,
		current_user,
		str(exclude_appointment_id) if exclude_appointment_id else None,
	)


@router.get("/reconcile", response_model=ReconciliationResponse)
async def reconcile_calendar(
	supabase: PublicSupabaseClient,
	authorization: str | None = Header(default=None),
) -> ReconciliationResponse:
	if not settings.CRON_SECRET:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Calendar reconciliation is not configured.",
		)
	expected = f"Bearer {settings.CRON_SECRET}"
	if not authorization or not secrets.compare_digest(authorization, expected):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Unauthorized.",
		)
	return await run_in_threadpool(reconcile_appointments, supabase)


@router.post(
	"/",
	response_model=AppointmentResponse,
	status_code=status.HTTP_201_CREATED,
)
async def send_appointment(
	payload: AppointmentPayload,
	response: Response,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
	google_access_token: str | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_COOKIE,
	),
	google_access_token_expires_at: int | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_EXPIRY_COOKIE,
	),
) -> AppointmentResponse:
	return await run_in_threadpool(
		create_appointment,
		payload,
		supabase,
		current_user,
		google_access_token,
		google_access_token_expires_at,
		response,
	)


@router.post(
	"/{appointment_id}/reschedule",
	response_model=AppointmentResponse,
)
async def update_appointment(
	appointment_id: UUID,
	payload: ReschedulePayload,
	response: Response,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
	google_access_token: str | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_COOKIE,
	),
	google_access_token_expires_at: int | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_EXPIRY_COOKIE,
	),
) -> AppointmentResponse:
	return await run_in_threadpool(
		reschedule_appointment,
		str(appointment_id),
		payload,
		supabase,
		current_user,
		google_access_token,
		google_access_token_expires_at,
		response,
	)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_appointment(
	appointment_id: UUID,
	response: Response,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
	google_access_token: str | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_COOKIE,
	),
	google_access_token_expires_at: int | None = Cookie(
		default=None,
		alias=GOOGLE_ACCESS_EXPIRY_COOKIE,
	),
) -> None:
	await run_in_threadpool(
		cancel_appointment,
		str(appointment_id),
		supabase,
		current_user,
		google_access_token,
		google_access_token_expires_at,
		response,
	)
