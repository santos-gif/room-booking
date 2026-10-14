import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, tap } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { MyBookingsService } from '../services/my-bookings.service';
import { Appointment } from '../types/my-bookings';

@Component({
	selector: 'app-my-bookings-page',
	templateUrl: './my-bookings-page.html',
	styleUrl: './my-bookings-page.css',
	providers: [MyBookingsService]
})
export class MyBookingsPage {
	private readonly myBookingsApi = inject(MyBookingsService);
	private readonly auth = inject(AuthService);
	private readonly router = inject(Router);
	private readonly reload = signal(0);
	readonly errorMessage = signal('');
	readonly calendarReconnectNeeded = signal(false);
	readonly busyId = signal('');
	readonly appointments = toSignal(
		toObservable(this.reload).pipe(
			switchMap(() =>
				this.myBookingsApi.list().pipe(
					tap(() => this.errorMessage.set('')),
					catchError(() => {
						this.errorMessage.set(
							'Unable to load your bookings. Please try again.',
						);
						return of([] as Appointment[]);
					}),
				),
			),
		),
		{ initialValue: [] as Appointment[] },
	);

	addAppointment(): void {
		void this.router.navigate(['/booking-form']);
	}

	reschedule(appointment: Appointment): void {
		void this.router.navigate(['/booking-form'], {
			queryParams: { reschedule: appointment.id },
		});
	}

	cancel(appointment: Appointment): void {
		if (!window.confirm('Cancel this appointment?')) {
			return;
		}
		this.busyId.set(appointment.id);
		this.myBookingsApi.cancel(appointment.id).subscribe({
			next: () => {
				this.busyId.set('');
				this.reload.update((value) => value + 1);
			},
			error: (error: { status?: number; error?: { detail?: string } }) => {
				this.busyId.set('');
				this.calendarReconnectNeeded.set(error.status === 401);
				this.errorMessage.set(
					error.status === 401 && error.error?.detail
						? error.error.detail
						: 'Unable to cancel this appointment. It has not been removed.',
				);
			},
		});
	}

	reconnectCalendar(): void {
		this.auth.login();
	}

	formatTime(value: string): string {
		return new Intl.DateTimeFormat('en-GB', {
			timeZone: 'Asia/Jakarta',
			hour: '2-digit',
			minute: '2-digit',
			hourCycle: 'h23',
		}).format(new Date(value));
	}
}
