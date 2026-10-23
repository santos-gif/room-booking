import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { BookingsStore } from '../../../core/services/bookings-store';

/**
 * What the My bookings page may do with the student's bookings: read the list, refresh it, cancel
 * one. A filter over the shared store, which the Booking form page also uses: this page sees the
 * list read-only and cannot reach the store's other methods (such as invalidating the cache).
 */
@Injectable()
export class MyBookingsService {
	private readonly store = inject(BookingsStore);

	readonly appointments = this.store.appointments.asReadonly();
	/** False until the first answer, and again after a booking changed. */
	readonly loaded = this.store.loaded.asReadonly();
	readonly error = this.store.error.asReadonly();

	/** Asks the server unless the list is younger than `maxAgeMs` (the store's default when omitted). */
	refresh(maxAgeMs?: number): void {
		this.store.refresh(maxAgeMs);
	}

	cancel(id: string): Observable<void> {
		return this.store.cancel(id);
	}
}
