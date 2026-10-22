import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth-service';
import { jakartaDate, jakartaToday } from '../../../core/utils/jakarta-today';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { BookingControls } from '../components/booking-controls/booking-controls';
import { ConfirmPanel } from '../components/confirm-panel/confirm-panel';
import { ResultDialog } from '../components/result-dialog/result-dialog';
import { SlotGrid } from '../components/slot-grid/slot-grid';
import { loadAvailability } from '../services/availability-loader';
import { BookingFormService } from '../services/booking-form.service';
import { AvailableSlot, BookingAppointment, BookingPayload } from '../types/booking-form';

const FAILED = 'Unable to complete the booking. Your existing booking was preserved.';
const TAKEN = 'That time slot is no longer available, or you already hold 3 upcoming bookings.';
const NOT_FOUND = 'We could not find that booking. Open Update from My bookings again.';

@Component({
	providers: [BookingFormService],
	imports: [AppHeader, BookingControls, ConfirmPanel, ResultDialog, SlotGrid],
	selector: 'app-booking-form-page',
	templateUrl: './booking-form-page.html',
	styleUrl: './booking-form-page.css',
})
export class BookingFormPage {
	private readonly api = inject(BookingFormService);
	private readonly auth = inject(AuthService);
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
	readonly slots = this.availability.slots;
	readonly bookingsRemaining = this.availability.bookingsRemaining;
	readonly loading = this.availability.loading;
	// The pick is remembered by start time; the slot itself comes from the newest answer, so the
	// drawer disappears with a stale list and when someone else takes the slot.
	private readonly selectedStart = signal<string | null>(null);
	readonly selectedSlot = computed(
		() =>
			this.slots().find(
				(s) => s.start_time === this.selectedStart() && s.available,
			) ?? null,
	);
	private readonly formError = signal('');
	readonly errorMessage = computed(() => this.availability.error() || this.formError());
	readonly resultMessage = signal('');
	readonly calendarReconnectNeeded = signal(false);
	readonly submitting = signal(false);
	private readonly saved = signal(false);
	private readonly current = signal<BookingAppointment | null>(null);
	/** Start of the booking being updated, only while its own room is showing (to outline it). */
	readonly currentStart = computed(() => {
		const current = this.current();
		return current && current.room_number === this.roomNumber()
			? current.start_time
			: null;
	});
	readonly noFreeSlot = computed(
		() =>
			!this.loading() &&
			this.slots().length > 0 &&
			!this.slots().some((slot) => slot.available),
	);

	constructor() {
		if (this.rescheduleId) {
			this.api.mine().subscribe({
				next: (list) => this.showCurrent(list),
				error: () => this.formError.set(NOT_FOUND),
			});
		}
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

	confirmBooking(): void {
		const slot = this.selectedSlot();
		if (!slot || this.submitting()) {
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
			error: (error: { status?: number; error?: { detail?: unknown } }) => {
				const detail = error.error?.detail;
				this.calendarReconnectNeeded.set(error.status === 401);
				this.finish(
					error.status === 409
						? TAKEN
						: typeof detail === 'string'
							? detail
							: FAILED,
				);
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

	reconnectCalendar(): void {
		this.auth.login();
	}

	// Success or not, ask again: a booked or just-taken slot must disappear from the grid now.
	private finish(message: string): void {
		this.submitting.set(false);
		this.resultMessage.set(message);
		this.reload.update((n) => n + 1);
	}

	private showCurrent(list: BookingAppointment[]): void {
		const current = list.find((a) => a.id === this.rescheduleId);
		if (!current) {
			this.formError.set(NOT_FOUND);
			return;
		}
		this.current.set(current);
		this.roomNumber.set(current.room_number);
		this.bookingDate.set(jakartaDate(new Date(current.start_time)));
	}
}
