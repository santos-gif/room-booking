from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from starlette.concurrency import run_in_threadpool

from app.api.v1.auth.types import AuthenticatedUser
from app.api.v1.staff import closures, override
from app.api.v1.staff.access import require_staff
from app.api.v1.staff.types import (
	ClosurePayload,
	ClosureResponse,
	OverridePayload,
	OverrideResult,
	StaffActionResult,
	StaffBooking,
)
from app.database import SupabaseClient

router = APIRouter(prefix="/staff", dependencies=[Depends(require_staff)])


@router.get("/closures", response_model=list[ClosureResponse])
async def get_closures(supabase: SupabaseClient) -> list[ClosureResponse]:
	return await run_in_threadpool(closures.listing, supabase)


@router.get("/closures/preview", response_model=list[StaffBooking])
async def preview_closure(
	supabase: SupabaseClient,
	start_date: date,
	end_date: date,
	room_number: int = Query(ge=1, le=2),
) -> list[StaffBooking]:
	return await run_in_threadpool(closures.preview, supabase, room_number, start_date, end_date)


@router.post("/closures", response_model=StaffActionResult, status_code=status.HTTP_201_CREATED)
async def create_closure(payload: ClosurePayload, supabase: SupabaseClient) -> StaffActionResult:
	return await run_in_threadpool(closures.create, supabase, payload)


@router.delete("/closures/{closure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_closure(closure_id: UUID, supabase: SupabaseClient) -> None:
	await run_in_threadpool(closures.remove, supabase, str(closure_id))


@router.get("/slot", response_model=list[StaffBooking])
async def get_slot_holder(
	supabase: SupabaseClient,
	start_time: datetime,
	room_number: int = Query(ge=1, le=2),
) -> list[StaffBooking]:
	return await run_in_threadpool(override.holder, supabase, room_number, start_time)


@router.post("/override", response_model=OverrideResult)
async def override_slot(
	payload: OverridePayload,
	supabase: SupabaseClient,
	staff: AuthenticatedUser = Depends(require_staff),
) -> OverrideResult:
	return await run_in_threadpool(override.override, supabase, staff, payload)
