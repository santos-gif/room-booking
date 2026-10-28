from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from starlette.concurrency import run_in_threadpool

from app.api.v1.appointment.booking import create_appointment, list_appointments
from app.api.v1.appointment.booking_date import BookingDate
from app.api.v1.appointment.cancel import cancel_appointment
from app.api.v1.appointment.reconcile import reconcile_appointments, require_cron_secret
from app.api.v1.appointment.reschedule import reschedule_appointment
from app.api.v1.appointment.slots import get_availability
from app.api.v1.appointment.types import (
	AppointmentPayload,
	AppointmentResponse,
	AvailabilityResponse,
	NoticeResponse,
	ReconciliationResponse,
	ReschedulePayload,
)
from app.api.v1.appointment.verify import verify_appointments
from app.api.v1.auth.helper import get_current_user
from app.api.v1.auth.types import AuthenticatedUser
from app.database import PublicSupabaseClient, SupabaseClient
from app.queries import staff as staff_queries

router = APIRouter(prefix="/appointments")


@router.get("/", response_model=list[AppointmentResponse])
async def get_appointments(
	supabase: SupabaseClient,
	verify: bool = False,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[AppointmentResponse]:
	if verify:
		return await run_in_threadpool(verify_appointments, supabase, current_user)
	return await run_in_threadpool(list_appointments, supabase, current_user)


@router.get("/availability", response_model=AvailabilityResponse)
async def get_available_slots(
	supabase: SupabaseClient,
	booking_date: BookingDate,
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


@router.get("/notices", response_model=list[NoticeResponse])
async def get_notices(
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[NoticeResponse]:
	return await run_in_threadpool(staff_queries.list_notices, supabase)


@router.post("/notices/{notice_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_notice(
	notice_id: UUID,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
	await run_in_threadpool(staff_queries.dismiss_notice, supabase, str(notice_id))


@router.get("/reconcile", response_model=ReconciliationResponse)
async def reconcile_calendar(
	supabase: PublicSupabaseClient,
	authorization: str | None = Header(default=None),
) -> ReconciliationResponse:
	require_cron_secret(authorization)
	return await run_in_threadpool(reconcile_appointments, supabase)


@router.post(
	"/",
	response_model=AppointmentResponse,
	status_code=status.HTTP_201_CREATED,
)
async def send_appointment(
	payload: AppointmentPayload,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> AppointmentResponse:
	return await run_in_threadpool(
		create_appointment,
		payload,
		supabase,
		current_user,
	)


@router.post(
	"/{appointment_id}/reschedule",
	response_model=AppointmentResponse,
)
async def update_appointment(
	appointment_id: UUID,
	payload: ReschedulePayload,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> AppointmentResponse:
	return await run_in_threadpool(
		reschedule_appointment,
		str(appointment_id),
		payload,
		supabase,
		current_user,
	)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_appointment(
	appointment_id: UUID,
	supabase: SupabaseClient,
	current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
	await run_in_threadpool(
		cancel_appointment,
		str(appointment_id),
		supabase,
		current_user,
	)
