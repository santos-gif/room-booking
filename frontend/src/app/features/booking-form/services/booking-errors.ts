const FAILED = 'Unable to complete the booking. Your existing booking was preserved.';
/** Shown while an update page is closing because its booking no longer exists. */
export const NOT_FOUND = 'We could not find that booking. Open Update from My bookings again.';
const TAKEN = 'That time slot is no longer available, or you already hold 3 upcoming bookings.';

export interface BookingFailure {
	message: string;
	/** Google rejected the Calendar token: offer "Reconnect Google Calendar". */
	reconnect: boolean;
}

/** Turns a failed book/update call into what the student sees. Never shows a non-string detail. */
export function describeBookingFailure(error: {
	status?: number;
	error?: { detail?: unknown };
}): BookingFailure {
	const detail = error.error?.detail;
	return {
		reconnect: error.status === 401,
		message: error.status === 409 ? TAKEN : typeof detail === 'string' ? detail : FAILED,
	};
}
