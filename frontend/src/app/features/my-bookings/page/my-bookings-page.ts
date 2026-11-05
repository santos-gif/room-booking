import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { scan, skip, Subscription } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';
import { BookingsStore } from '../../../shared/stores/bookings-store';
import { Appointment } from '../../../core/types/appointment';
import { visibleTimer } from '../../../shared/helpers/visible-timer';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ConfirmDialog } from '../../../shared/components/confirm-dialog/confirm-dialog';
import { BookingCard } from '../components/booking-card/booking-card';
import { EmptyState } from '../components/empty-state/empty-state';
import { NoticesService } from '../services/notices.service';
import { Notice } from '../types/notice';
import { DIALOG_WIDTH } from '../../../shared/helpers/dialog-width';

const CANCEL_FAILED = 'Unable to cancel this appointment. It has not been removed.';
const NOTICES_FAILED = 'Unable to check for messages from staff. They will show once it works.';
// A tick every 35 s, just over the backend's 30 s check cooldown, so every poll really asks Google.
const POLL_MS = 35_000;
// A list is "too old" after 30 s: the response of the previous poll lands a moment after its tick, so a
// 35 s limit would see it as still fresh and skip every other tick (a 70 s period).
const STALE_MS = 30_000;
// After a failed notices load the poll skips the route this long, like the bookings store does.
const NOTICES_RETRY_MS = 60_000;

@Component({
	providers: [NoticesService],
	imports: [AppHeader, BookingCard, EmptyState],
	selector: 'app-my-bookings-page',
	templateUrl: './my-bookings-page.html',
	styleUrl: './my-bookings-page.css',
})
export class MyBookingsPage {
	private readonly bookings = inject(BookingsStore);
	private readonly router = inject(Router);
	private readonly dialog = inject(MatDialog);
	private readonly noticeApi = inject(NoticesService);
	/** Messages about bookings staff cancelled, until the student dismisses them. */
	readonly notices = signal<Notice[]>([]);
	private readonly cancelError = signal('');
	private readonly noticeError = signal('');
	private noticesCall: Subscription | null = null;
	private noticesFailedAt = 0;
	/** Dismissed here: a list that was already on its way must not bring them back. */
	private readonly dismissed = new Set<string>();
	readonly errorMessage = computed(
		() => this.cancelError() || this.bookings.error() || this.noticeError(),
	);
	readonly busyId = signal('');
	// False until the first answer: the list panel shows placeholders, not the empty message.
	readonly loaded = this.bookings.loaded.asReadonly();
	readonly appointments = this.bookings.appointments.asReadonly();

	// Counts the page opening (0), then every poll and every return to the tab. The timer's own
	// first emission is skipped: the count already starts at 0, so the page opening asks once.
	private readonly ticks = toSignal(
		visibleTimer(POLL_MS).pipe(
			skip(1),
			scan((n) => n + 1, 0),
		),
		{
			initialValue: 0,
		},
	);
	// Shows the cached list at once; the store only calls the server when the cache is stale. While
	// this tab is open it also notices a booking whose Google event was deleted, or a staff
	// cancellation and its message, without a reload.
	protected readonly poll = effect(() => {
		this.ticks();
		untracked(() => {
			this.bookings.refresh(STALE_MS);
			if (Date.now() - this.noticesFailedAt >= NOTICES_RETRY_MS) {
				this.loadNotices();
			}
		});
	});

	dismissNotice(id: string): void {
		this.dismissed.add(id);
		this.notices.update((list) => list.filter((notice) => notice.id !== id));
		this.noticeApi.dismiss(id).subscribe({
			error: () => {
				this.dismissed.delete(id);
				this.loadNotices();
			},
		});
	}

	/** Only the newest answer counts: an older request still on its way is dropped. */
	private loadNotices(): void {
		this.noticesCall?.unsubscribe();
		this.noticesCall = this.noticeApi.list().subscribe({
			next: (list) => {
				this.notices.set(
					list.filter((notice) => !this.dismissed.has(notice.id)),
				);
				this.noticeError.set('');
			},
			error: () => {
				this.noticesFailedAt = Date.now();
				this.noticeError.set(NOTICES_FAILED);
			},
		});
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
