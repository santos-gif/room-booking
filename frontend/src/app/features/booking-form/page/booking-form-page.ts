import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth-service';
import { jakartaToday } from '../../../core/utils/jakarta-today';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { BookingControls } from '../components/booking-controls/booking-controls';
import { ConfirmPanel } from '../components/confirm-panel/confirm-panel';
import { ResultDialog } from '../components/result-dialog/result-dialog';
import { SlotGrid } from '../components/slot-grid/slot-grid';
import { loadAvailability } from '../services/availability-loader';
import { describeBookingFailure, NOT_FOUND } from '../services/booking-errors';
import { BookingFormService } from '../services/booking-form.service';
import { guardBookingPage } from '../services/page-lifecycle';
import { loadUpdateTarget } from '../services/update-target';
import { AvailableSlot, BookingPayload } from '../types/booking-form';

@Component({
	providers: [BookingFormService],
	imports: [AppHeader, BookingControls, ConfirmPanel, ResultDialog, SlotGrid],
	selector: 'app-booking-form-page',
	templateUrl: './booking-form-page.html',
	styleUrl: './booking-form-page.css',
})
export class BookingFormPage {
	private readonly api = inject(BookingFormService);
	protected readonly auth = inject(AuthService);
	private readonly router = inject(Router);
	// Set when arriving from "Update" on My bookings: that booking is moved instead of a new one made.
	private readonly rescheduleId =
		inject(ActivatedRoute).snapshot.queryParamMap.get('reschedule');
	readonly updating = this.rescheduleId !== null;
	readonly bookingDate = signal(jakartaToday());
	readonly roomNumber = signal<1 | 2>(1);
	private readonly reload = signal(0);
	private readonly availability = loadAvailability(this.api, {
		date: this.bookingDate,
		room: this.roomNumber,
		reload: this.reload,
		excludeId: this.rescheduleId ?? undefined,
	});
	private readonly target = loadUpdateTarget(this.api, this.rescheduleId, {
		room: this.roomNumber,
		date: this.bookingDate,
		onOpen: () => this.selectedStart.set(null),
	});
	readonly slots = this.availability.slots;
	readonly bookingsRemaining = this.availability.bookingsRemaining;
	readonly loading = this.availability.loading;
	readonly availabilityError = this.availability.error;
	/** The booking being updated is gone: nothing can be saved and the page returns to My bookings. */
	readonly blocked = computed(() => this.target.missing() || this.availability.gone());
	private readonly selectedStart = signal<string | null>(null);
	readonly selectedSlot = computed(
		() =>
			this.slots().find(
				(s) => s.start_time === this.selectedStart() && s.available,
			) ?? null,
	);
	private readonly formError = signal('');
	readonly errorMessage = computed(
		() =>
			this.availabilityError() ||
			(this.blocked() ? NOT_FOUND : '') ||
			this.formError(),
	);
	readonly resultMessage = signal('');
	readonly calendarReconnectNeeded = signal(false);
	readonly submitting = signal(false);
	private readonly saved = signal(false);
	readonly currentStart = this.target.currentStart;
	readonly noFreeSlot = this.availability.noFreeSlot;

	constructor() {
		guardBookingPage(this.submitting, this.blocked, () => !!this.resultMessage());
	}

	changeRoom(room: 1 | 2): void {
		this.roomNumber.set(room);
		this.selectedStart.set(null);
	}

	changeDate(date: string): void {
		this.bookingDate.set(date);
		this.selectedStart.set(null);
	}

	pick(slot: AvailableSlot): void {
		this.selectedStart.set(slot.start_time);
	}

	clearSelection(): void {
		this.selectedStart.set(null);
	}

	/** After a failed load: ask the server again. */
	retry(): void {
		this.reload.update((n) => n + 1);
	}

	confirmBooking(): void {
		const slot = this.selectedSlot();
		if (!slot || this.submitting() || this.blocked()) {
			return;
		}
		this.submitting.set(true);
		this.formError.set('');
		this.calendarReconnectNeeded.set(false);
		const payload: BookingPayload = {
			room_number: this.roomNumber(),
			start_time: slot.start_time,
		};
		const request = this.rescheduleId
			? this.api.reschedule(this.rescheduleId, payload)
			: this.api.book(payload);
		request.subscribe({
			next: () => {
				this.saved.set(true);
				this.finish(
					this.updating
						? 'Booking updated successfully.'
						: 'Appointment booked successfully.',
				);
			},
			error: (error) => {
				const failure = describeBookingFailure(error);
				this.calendarReconnectNeeded.set(failure.reconnect);
				this.finish(failure.message);
			},
		});
	}

	closeResult(): void {
		this.resultMessage.set('');
		this.selectedStart.set(null);
		if (this.updating && this.saved()) {
			void this.router.navigate(['/my-bookings']);
		}
	}

	// Success or not, ask again: a booked or just-taken slot must disappear from the grid now.
	private finish(message: string): void {
		this.submitting.set(false);
		this.resultMessage.set(message);
		// A saved update ends on My bookings: asking again would 404 for the booking it just replaced.
		if (!(this.updating && this.saved())) {
			this.reload.update((n) => n + 1);
		}
	}
}
