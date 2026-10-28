export interface Closure {
	id: string;
	room_number: 1 | 2;
	start_date: string;
	end_date: string;
	reason: string;
}

/** A booking staff are about to cancel, or the one holding a slot. */
export interface StaffBooking {
	appointment_id: string;
	booker_name: string | null;
	booker_nim: number | null;
	booker_email: string;
	room_number: number;
	start_time: string;
	end_time: string;
}

export interface ClosurePayload {
	room_number: 1 | 2;
	start_date: string;
	end_date: string;
	reason: string;
}

export interface OverridePayload {
	room_number: 1 | 2;
	start_time: string;
	reason: string;
}

export interface StaffResult {
	cancelled: number;
	/** Cancelled bookings whose Google event is not deleted yet (the nightly job finishes them). */
	events_left: number;
}
