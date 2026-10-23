import { computed, effect, signal, untracked, WritableSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { jakartaDate } from '../../../shared/helpers/jakarta-today';
import { BookingAppointment } from '../types/booking-form';
import { BookingFormService } from '../service/booking-form.service';

interface UpdateView {
	room: WritableSignal<1 | 2>;
	date: WritableSignal<string>;
	/** Called when the booking is found and the view jumps to it (clear any stale selection). */
	onOpen: () => void;
}

/**
 * Update mode, everything about the booking being moved. Finds it, opens the page on its own room and
 * day, and tells the grid which time it has now. `missing` turns true when it is gone (cancelled,
 * deleted in Google Calendar, someone else's, or the lookup failed): nothing may be saved then, because
 * moving a booking that does not exist would only produce a confusing error. Pass null when not
 * updating. Call it in an injection context (a field initializer).
 */
export function loadUpdateTarget(api: BookingFormService, id: string | null, view: UpdateView) {
	const current = signal<BookingAppointment | null>(null);
	const missing = signal(false);
	if (id) {
		api.mine()
			.pipe(takeUntilDestroyed())
			.subscribe({
				next: (list) => {
					const found = list.find((booking) => booking.id === id);
					if (found) {
						current.set(found);
					} else {
						missing.set(true);
					}
				},
				error: () => missing.set(true),
			});
	}

	effect(() => {
		const booking = current();
		if (booking) {
			untracked(() => {
				view.room.set(booking.room_number);
				view.date.set(jakartaDate(new Date(booking.start_time)));
				view.onOpen();
			});
		}
	});

	/** Start of the booking while its own room shows, so the grid can label that time. */
	const currentStart = computed(() => {
		const booking = current();
		return booking && booking.room_number === view.room() ? booking.start_time : null;
	});
	return { missing, currentStart };
}
