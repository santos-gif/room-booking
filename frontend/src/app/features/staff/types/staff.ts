import { WritableSignal } from '@angular/core';

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

/** What the closures panel asks the page to preview: the room and the dates. */
export interface ClosureQuery {
	room: 1 | 2;
	start: string;
	end: string;
}

/** What the override panel asks the page to check: the room and one hour (ISO, Jakarta time). */
export interface SlotQuery {
	room: 1 | 2;
	startTime: string;
}

/** One panel's requests in flight (a count, so one answer never frees another's buttons) and its error. */
export interface Lane {
	pending: WritableSignal<number>;
	error: WritableSignal<string>;
}

export interface StaffResult {
	cancelled: number;
	/** Cancelled bookings whose Google event is not deleted yet (the nightly job finishes them). */
	events_left: number;
}
