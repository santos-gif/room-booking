import { describeBookingFailure } from './booking-errors';

describe('describeBookingFailure (what the student reads after a failed booking)', () => {
	it('explains a conflict or the 3-booking limit for a 409', () => {
		const failure = describeBookingFailure({ status: 409 });
		expect(failure.message).toContain('no longer available');
		expect(failure.reconnect).toBe(false);
	});

	it('offers a Calendar reconnect only for a 401 and shows the server wording', () => {
		const failure = describeBookingFailure({
			status: 401,
			error: { detail: 'Reconnect Google Calendar.' },
		});
		expect(failure).toEqual({ message: 'Reconnect Google Calendar.', reconnect: true });
	});

	it('never renders a non-string detail (FastAPI 422 sends a list), it falls back instead', () => {
		const failure = describeBookingFailure({
			status: 422,
			error: { detail: [{ msg: 'bad' }] },
		});
		expect(failure.message).toContain('Unable to complete the booking');
		expect(failure.message).not.toContain('object');
	});

	it('falls back when there is no detail at all (network error, 500)', () => {
		expect(describeBookingFailure({ status: 0 }).message).toContain(
			'Unable to complete',
		);
		expect(describeBookingFailure({}).message).toContain('Unable to complete');
	});

	it('tells the student to check My bookings after a timeout, since the save may have worked', () => {
		const message = describeBookingFailure({ name: 'TimeoutError' }).message;
		expect(message).toContain('My bookings');
		expect(message).not.toContain('preserved');
	});
});
