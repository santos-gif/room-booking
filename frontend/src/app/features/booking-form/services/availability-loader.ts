import { effect, Signal, signal } from '@angular/core';
import { catchError, EMPTY, switchMap } from 'rxjs';
import { visibleTimer } from '../../../core/utils/visible-timer';
import { AvailableSlot } from '../types/booking-form';
import { BookingFormService } from './booking-form.service';

interface AvailabilityQuery {
	date: Signal<string>;
	room: Signal<1 | 2>;
	/** Bump to force a fresh load (after a booking attempt). */
	reload: Signal<number>;
	/** The booking being updated: it must not count against the limit or its own slot. */
	excludeId?: string;
}

/**
 * Slots for the chosen day and room. At the start of every date, room or reload change the slots
 * are emptied and `loading` is true, so a list from another room can never show (or be clicked)
 * while the new answer is on its way. After that it refreshes every minute while the tab is visible.
 * Call it in an injection context (a field initializer).
 */
export function loadAvailability(api: BookingFormService, query: AvailabilityQuery) {
	const slots = signal<AvailableSlot[]>([]);
	const bookingsRemaining = signal(3);
	const loading = signal(true);
	const error = signal('');

	effect((onCleanup) => {
		const date = query.date();
		const room = query.room();
		query.reload();
		slots.set([]);
		loading.set(true);
		error.set('');
		const subscription = visibleTimer(60_000)
			.pipe(
				switchMap(() =>
					api.availability(date, room, query.excludeId).pipe(
						catchError(() => {
							error.set(
								'Unable to refresh availability. Please try again.',
							);
							loading.set(false);
							return EMPTY;
						}),
					),
				),
			)
			.subscribe((availability) => {
				slots.set(availability.slots);
				bookingsRemaining.set(availability.bookings_remaining);
				error.set('');
				loading.set(false);
			});
		onCleanup(() => subscription.unsubscribe());
	});

	return { slots, bookingsRemaining, loading, error };
}
