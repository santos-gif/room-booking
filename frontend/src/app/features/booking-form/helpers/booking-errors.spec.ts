import { describeBookingFailure } from './booking-errors';

describe('describeBookingFailure (what the student reads after a failed booking)', () => {
	it('explains a conflict or the 3-booking limit for a 409', () => {
		expect(describeBookingFailure({ status: 409 })).toContain('no longer available');
	});

	it('shows the server wording when it sent a sentence', () => {
		const failure = describeBookingFailure({
			status: 503,
			error: { detail: 'The room calendar is not available right now.' },
		});
		expect(failure).toBe('The room calendar is not available right now.');
	});

	it('never renders a non-string detail (FastAPI 422 sends a list), it falls back instead', () => {
		const failure = describeBookingFailure({
			status: 422,
			error: { detail: [{ msg: 'bad' }] },
		});
		expect(failure).toContain('Unable to complete the booking');
		expect(failure).not.toContain('object');
	});

	it('falls back when there is no detail at all (network error, 500)', () => {
		expect(describeBookingFailure({ status: 0 })).toContain('Unable to complete');
		expect(describeBookingFailure({})).toContain('Unable to complete');
	});

	it('tells the student to check My bookings after a timeout, since the save may have worked', () => {
		const message = describeBookingFailure({ name: 'TimeoutError' });
		expect(message).toContain('My bookings');
		expect(message).not.toContain('preserved');
	});
});
