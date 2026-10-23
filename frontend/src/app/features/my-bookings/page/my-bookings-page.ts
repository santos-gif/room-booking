import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { AuthService } from '../../../core/services/auth-service';
import { BookingsStore } from '../../../core/services/bookings-store';
import { Appointment } from '../../../core/types/appointment';
import { visibleTimer } from '../../../core/utils/visible-timer';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ConfirmDialog } from '../../../shared/components/confirm-dialog/confirm-dialog';
import { BookingCard } from '../components/booking-card/booking-card';
import { EmptyState } from '../components/empty-state/empty-state';

// A tick every 35 s, just over the backend's 30 s check cooldown, so every poll really asks Google.
const POLL_MS = 35_000;
// A list is "too old" after 30 s: the response of the previous poll lands a moment after its tick, so a
// 35 s limit would see it as still fresh and skip every other tick (a 70 s period).
const STALE_MS = 30_000;

@Component({
	imports: [AppHeader, BookingCard, EmptyState],
	selector: 'app-my-bookings-page',
	templateUrl: './my-bookings-page.html',
	styleUrl: './my-bookings-page.css',
})
export class MyBookingsPage {
	private readonly store = inject(BookingsStore);
	private readonly auth = inject(AuthService);
	private readonly router = inject(Router);
	private readonly dialog = inject(MatDialog);
	private readonly cancelError = signal('');
	readonly errorMessage = computed(() => this.cancelError() || this.store.error());
	readonly calendarReconnectNeeded = signal(false);
	readonly busyId = signal('');
	// False until the first answer: the list panel shows placeholders, not the empty message.
	readonly loaded = this.store.loaded;
	readonly appointments = this.store.appointments;

	constructor() {
		// Shows the cached list at once; the store only calls the server when the cache is stale.
		this.store.refresh();
		// While this tab is open, notice a booking whose Google event was deleted without a reload.
		visibleTimer(POLL_MS)
			.pipe(takeUntilDestroyed())
			.subscribe(() => this.store.refresh(STALE_MS));
	}

	addAppointment(): void {
		void this.router.navigate(['/booking-form']);
	}

	update(appointment: Appointment): void {
		void this.router.navigate(['/booking-form'], {
			queryParams: { reschedule: appointment.id },
		});
	}

	askToCancel(appointment: Appointment): void {
		this.dialog
			.open<ConfirmDialog, unknown, boolean>(ConfirmDialog, {
				width: '400px',
				data: {
					title: 'Cancel this booking?',
					message: 'The slot is freed for other people',
					confirmLabel: 'Cancel booking',
					cancelLabel: 'Keep booking',
				},
			})
			.afterClosed()
			.subscribe((confirmed) => {
				if (confirmed) {
					this.cancel(appointment);
				}
			});
	}

	private cancel(appointment: Appointment): void {
		this.busyId.set(appointment.id);
		this.cancelError.set('');
		this.calendarReconnectNeeded.set(false);
		this.store.cancel(appointment.id).subscribe({
			next: () => this.busyId.set(''),
			error: (error: { status?: number; error?: { detail?: unknown } }) => {
				const detail = error.error?.detail;
				this.busyId.set('');
				this.calendarReconnectNeeded.set(error.status === 401);
				this.cancelError.set(
					error.status === 401 && typeof detail === 'string'
						? detail
						: 'Unable to cancel this appointment. It has not been removed.',
				);
			},
		});
	}

	reconnectCalendar(): void {
		this.auth.login();
	}
}
