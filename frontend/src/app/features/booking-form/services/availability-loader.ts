import { computed, effect, Signal, signal } from '@angular/core';
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

/** What a student may hold at once (the server enforces it; this is only the number shown before the first answer). */
const BOOKING_LIMIT = 3;
/** How often a visible tab asks again, so a slot someone else just took disappears. */
const REFRESH_MS = 60_000;

/**
 * Slots for the chosen day and room. At the start of every date, room or reload change the slots
 * are emptied and `loading` is true, so a list from another room can never show (or be clicked)
 * while the new answer is on its way. After that it refreshes every minute while the tab is visible.
 * Call it in an injection context (a field initializer).
 */
export function loadAvailability(api: BookingFormService, query: AvailabilityQuery) {
	const slots = signal<AvailableSlot[]>([]);
	const bookingsRemaining = signal(BOOKING_LIMIT);
	const loading = signal(true);
	const error = signal('');
	/** The booking being updated no longer exists (the server answers 404 for it). */
	const gone = signal(false);

	effect((onCleanup) => {
		const date = query.date();
		const room = query.room();
		query.reload();
		slots.set([]);
		loading.set(true);
		error.set('');
		const subscription = visibleTimer(REFRESH_MS)
			.pipe(
				switchMap(() =>
					api.availability(date, room, query.excludeId).pipe(
						catchError((failure: { status?: number }) => {
							// 404 can only mean the excluded booking is gone: the route itself exists.
							gone.set(
								failure.status === 404 &&
									!!query.excludeId,
							);
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

	/** Loaded, there are slots, and every one is taken (not the same as "nothing loaded yet"). */
	const noFreeSlot = computed(
		() => !loading() && slots().length > 0 && !slots().some((slot) => slot.available),
	);

	return { slots, bookingsRemaining, loading, error, noFreeSlot, gone };
}
