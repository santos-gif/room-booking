import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { Appointment } from '../../../core/types/appointment';
import { visibleTimer } from '../../../shared/helpers/visible-timer';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ConfirmDialog } from '../../../shared/components/confirm-dialog/confirm-dialog';
import { BookingCard } from '../components/booking-card/booking-card';
import { EmptyState } from '../components/empty-state/empty-state';
import { MyBookingsService } from '../service/my-bookings.service';
import { NoticesService } from '../service/notices.service';
import { DIALOG_WIDTH } from '../../../shared/helpers/dialog-width';

const CANCEL_FAILED = 'Unable to cancel this appointment. It has not been removed.';
// A tick every 35 s, just over the backend's 30 s check cooldown, so every poll really asks Google.
const POLL_MS = 35_000;
// A list is "too old" after 30 s: the response of the previous poll lands a moment after its tick, so a
// 35 s limit would see it as still fresh and skip every other tick (a 70 s period).
const STALE_MS = 30_000;

@Component({
	providers: [MyBookingsService],
	imports: [AppHeader, BookingCard, EmptyState],
	selector: 'app-my-bookings-page',
	templateUrl: './my-bookings-page.html',
	styleUrl: './my-bookings-page.css',
})
export class MyBookingsPage {
	private readonly bookings = inject(MyBookingsService);
	private readonly router = inject(Router);
	private readonly dialog = inject(MatDialog);
	private readonly noticeApi = inject(NoticesService);
	/** Messages about bookings staff cancelled, until the student dismisses them. */
	readonly notices = this.noticeApi.notices;
	private readonly cancelError = signal('');
	readonly errorMessage = computed(() => this.cancelError() || this.bookings.error());
	readonly busyId = signal('');
	// False until the first answer: the list panel shows placeholders, not the empty message.
	readonly loaded = this.bookings.loaded;
	readonly appointments = this.bookings.appointments;

	constructor() {
		// Shows the cached list at once; the store only calls the server when the cache is stale.
		this.bookings.refresh();
		this.noticeApi.load();
		// While this tab is open, notice a booking whose Google event was deleted without a reload.
		visibleTimer(POLL_MS)
			.pipe(takeUntilDestroyed())
			.subscribe(() => this.bookings.refresh(STALE_MS));
	}

	dismissNotice(id: string): void {
		this.noticeApi.dismiss(id);
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
				width: DIALOG_WIDTH,
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
		this.bookings.cancel(appointment.id).subscribe({
			next: () => this.busyId.set(''),
			error: () => {
				this.busyId.set('');
				this.cancelError.set(CANCEL_FAILED);
			},
		});
	}
}
