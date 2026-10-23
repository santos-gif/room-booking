import { ApiFailure, serverDetail } from '../../../core/utils/api-failure';

const FAILED = 'Unable to complete the booking. Your existing booking was preserved.';
/** Shown while an update page is closing because its booking no longer exists. */
export const NOT_FOUND = 'We could not find that booking. Open Update from My bookings again.';
/** No answer in time: the server may or may not have saved it, so say what to check. */
const NO_ANSWER =
	'The server took too long to answer. Open My bookings to see whether it was saved before you try again.';
const TAKEN = 'That time slot is no longer available, or you already hold 3 upcoming bookings.';

export interface BookingFailure {
	message: string;
	/** Google rejected the Calendar token: offer "Reconnect Google Calendar". */
	reconnect: boolean;
}

/** Turns a failed book/update call into what the student sees. Never shows a non-string detail. */
export function describeBookingFailure(error: ApiFailure): BookingFailure {
	return {
		reconnect: error.status === 401,
		message: describe(error),
	};
}

function describe(error: ApiFailure): string {
	if (error.name === 'TimeoutError') {
		return NO_ANSWER;
	}
	return error.status === 409 ? TAKEN : (serverDetail(error) ?? FAILED);
}
