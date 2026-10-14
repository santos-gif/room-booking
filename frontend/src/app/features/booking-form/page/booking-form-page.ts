import { DatePipe } from '@angular/common';
import {
	Component,
	effect,
	inject,
	signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, EMPTY, switchMap, timer } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { BookingFormService } from '../services/booking-form.service';
import {
	Availability,
	AvailableSlot,
	BookingPayload,
} from '../types/booking-form';

@Component({
	providers: [BookingFormService],
	imports: [DatePipe, FormsModule],
	selector: 'app-booking-form-page',
	templateUrl: './booking-form-page.html',
	styleUrl: './booking-form-page.css',
})
export class BookingFormPage {
	private readonly bookingFormApi = inject(BookingFormService);
	private readonly auth = inject(AuthService);
	readonly bookingDate = signal(this.jakartaToday());
	readonly roomNumber = signal<1 | 2>(1);
	readonly slots = signal<AvailableSlot[]>([]);
	readonly bookingsRemaining = signal(2);
	readonly selectedSlot = signal<AvailableSlot | null>(null);
	readonly errorMessage = signal('');
	readonly resultMessage = signal('');
	readonly calendarReconnectNeeded = signal(false);
	readonly loading = signal(true);
	readonly submitting = signal(false);

	private readonly availabilityEffect = effect((onCleanup) => {
		const date = this.bookingDate();
		const roomNumber = this.roomNumber();
		this.loading.set(true);
		this.errorMessage.set('');
		const subscription = timer(0, 30_000)
			.pipe(
				switchMap(() =>
					this.bookingFormApi
						.availability(date, roomNumber)
						.pipe(
							catchError(() => {
								this.errorMessage.set(
									'Unable to refresh availability. Please try again.',
								);
								this.loading.set(false);
								return EMPTY;
							}),
						),
				),
			)
			.subscribe((availability) => {
				this.updateAvailability(availability);
				this.loading.set(false);
			});
		onCleanup(() => subscription.unsubscribe());
	});

	setRoom(event: Event): void {
		const input = event.target;
		if (!(input instanceof HTMLInputElement)) {
			return;
		}
		const room = Number(input.value);
		if (room === 1 || room === 2) {
			this.roomNumber.set(room);
			this.selectedSlot.set(null);
		}
	}

	book(slot: AvailableSlot): void {
		this.selectedSlot.set(slot);
	}

	confirmBooking(): void {
		const slot = this.selectedSlot();
		if (!slot || this.submitting()) {
			return;
		}
		this.submitting.set(true);
		this.errorMessage.set('');
		const payload: BookingPayload = {
			room_number: this.roomNumber(),
			start_time: slot.start_time,
		};
		this.bookingFormApi.book(payload).subscribe({
			next: () => {
				this.submitting.set(false);
				this.resultMessage.set('Appointment booked successfully.');
			},
			error: (error: { status?: number; error?: { detail?: string } }) => {
				this.submitting.set(false);
				this.calendarReconnectNeeded.set(error.status === 401);
				this.resultMessage.set(
					error.status === 409
						? 'That time slot is no longer available or your daily limit has been reached.'
						: error.error?.detail ??
						'Unable to complete the booking. Your existing booking was preserved.',
				);
			},
		});
	}

	closeResult(): void {
		this.resultMessage.set('');
		this.selectedSlot.set(null);
	}

	reconnectCalendar(): void {
		this.auth.login();
	}

	private updateAvailability(availability: Availability): void {
		this.slots.set(availability.slots);
		this.bookingsRemaining.set(availability.bookings_remaining);
		const selected = this.selectedSlot();
		if (
			selected
			&& !availability.slots.some(
				(slot) => slot.start_time === selected.start_time && slot.available,
			)
		) {
			this.selectedSlot.set(null);
		}
	}

	private jakartaToday(): string {
		const parts = new Intl.DateTimeFormat('en-CA', {
			timeZone: 'Asia/Jakarta',
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
		}).formatToParts(new Date());
		const part = (type: string): string =>
			parts.find((item) => item.type === type)?.value ?? '';
		return `${part('year')}-${part('month')}-${part('day')}`;
	}
}
