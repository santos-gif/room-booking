import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatDialog } from '@angular/material/dialog';
import { catchError, EMPTY, switchMap, tap } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ConfirmDialog } from '../../../shared/components/confirm-dialog/confirm-dialog';
import { BookingCard } from '../components/booking-card/booking-card';
import { EmptyState } from '../components/empty-state/empty-state';
import { MyBookingsService } from '../services/my-bookings.service';
import { Appointment } from '../types/my-bookings';

@Component({
	imports: [AppHeader, BookingCard, EmptyState],
	selector: 'app-my-bookings-page',
	templateUrl: './my-bookings-page.html',
	styleUrl: './my-bookings-page.css',
	providers: [MyBookingsService],
})
export class MyBookingsPage {
	private readonly myBookingsApi = inject(MyBookingsService);
	private readonly auth = inject(AuthService);
	private readonly router = inject(Router);
	private readonly dialog = inject(MatDialog);
	private readonly reload = signal(0);
	readonly errorMessage = signal('');
	readonly calendarReconnectNeeded = signal(false);
	readonly busyId = signal('');
	// False until the first response: the list panel shows placeholders, not the empty message.
	readonly loaded = signal(false);
	readonly appointments = toSignal(
		toObservable(this.reload).pipe(
			switchMap(() =>
				this.myBookingsApi.list().pipe(
					tap(() => {
						this.errorMessage.set('');
						this.loaded.set(true);
					}),
					catchError(() => {
						this.errorMessage.set(
							'Unable to load your bookings. Please try again.',
						);
						this.loaded.set(true);
						// Keep whatever list is already on screen: a failed reload must not look like "no bookings".
						return EMPTY;
					}),
				),
			),
		),
		{ initialValue: [] as Appointment[] },
	);

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
					message: 'The slot is freed for other students and the Google Calendar event is removed.',
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
		this.calendarReconnectNeeded.set(false);
		this.myBookingsApi.cancel(appointment.id).subscribe({
			next: () => {
				this.busyId.set('');
				this.reload.update((value) => value + 1);
			},
			error: (error: { status?: number; error?: { detail?: unknown } }) => {
				const detail = error.error?.detail;
				this.busyId.set('');
				this.calendarReconnectNeeded.set(error.status === 401);
				this.errorMessage.set(
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
