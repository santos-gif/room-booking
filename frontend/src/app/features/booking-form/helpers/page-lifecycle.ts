import { DestroyRef, effect, inject, Signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import { NavigationLock } from '../../../core/services/navigation-lock';
import { BookingFormService } from '../service/booking-form.service';

/**
 * Two page-wide rules. While `saving` the navbar and back button are locked, so the page cannot be
 * left half way through a save. When `gone` turns true (the booking being updated no longer exists)
 * the student goes back to My bookings with a fresh list, once the save has ended and any result
 * dialog (which may explain why) is closed. Call it in an injection context.
 */
export function guardBookingPage(
	saving: Signal<boolean>,
	gone: Signal<boolean>,
	holdRedirect: () => boolean,
): void {
	const lock = inject(NavigationLock);
	const router = inject(Router);
	const api = inject(BookingFormService);
	effect(() => lock.locked.set(saving()));
	inject(DestroyRef).onDestroy(() => lock.locked.set(false));
	effect(() => {
		if (gone() && !saving() && !holdRedirect()) {
			untracked(() => {
				api.invalidateBookings();
				void router.navigate(['/my-bookings']);
			});
		}
	});
}
