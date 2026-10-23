import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Appointment } from '../types/appointment';

const FRESH_MS = 60_000;

/**
 * The student's upcoming bookings, cached for the whole session and shared by every page.
 * Opening My bookings shows what is cached at once and asks the server only when the cache is older
 * than a minute. That ask uses verify=true, so the backend also checks Google Calendar and a booking
 * whose event was deleted there disappears here. Making or updating a booking invalidates the cache.
 */
@Injectable({ providedIn: 'root' })
export class BookingsStore {
	private readonly http = inject(HttpClient);
	private readonly baseUrl = `${environment.apiUrl}/appointments`;
	readonly appointments = signal<Appointment[]>([]);
	/** False until the first answer, and again after a booking changed: the list cannot be trusted then. */
	readonly loaded = signal(false);
	readonly error = signal('');
	private fetchedAt = 0;
	private version = 0;
	private loading = false;

	/** Asks the server unless the list is younger than `maxAgeMs` (a minute by default). */
	refresh(maxAgeMs = FRESH_MS): void {
		if (this.loading || Date.now() - this.fetchedAt < maxAgeMs) {
			return;
		}
		this.loading = true;
		const version = this.version;
		const params = new HttpParams().set('verify', 'true');
		this.http.get<Appointment[]>(`${this.baseUrl}/`, { params }).subscribe({
			next: (list) => {
				this.loading = false;
				if (version !== this.version) {
					// A booking changed while this was on its way: this answer is stale, ask again.
					this.refresh();
					return;
				}
				this.appointments.set(list);
				this.error.set('');
				this.fetchedAt = Date.now();
				this.loaded.set(true);
			},
			error: () => {
				this.loading = false;
				// Keep a still-trustworthy cached list; but after a booking changed (fetchedAt reset) the
				// old list is wrong, so show the error alone rather than a list that looks current.
				if (this.fetchedAt === 0) {
					this.appointments.set([]);
				}
				this.error.set('Unable to load your bookings. Please try again.');
				this.loaded.set(true);
			},
		});
	}

	/** Call after a booking was made or moved: the cached list is wrong until the next refresh. */
	invalidate(): void {
		this.version++;
		this.fetchedAt = 0;
		this.loaded.set(false);
	}

	cancel(id: string): Observable<void> {
		return this.http.delete<void>(`${this.baseUrl}/${id}`).pipe(
			tap(() => {
				this.appointments.update((list) => list.filter((a) => a.id !== id));
				// A list request that started before this cancel would bring the booking back: drop it.
				this.version++;
				this.fetchedAt = 0;
			}),
		);
	}
}
