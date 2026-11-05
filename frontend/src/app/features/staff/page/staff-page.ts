import { Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { MatDialog } from '@angular/material/dialog';
import { finalize, Observable, Subscription } from 'rxjs';
import { serverDetail } from '../../../core/utils/api-failure';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ConfirmDialog } from '../../../shared/components/confirm-dialog/confirm-dialog';
import { DIALOG_WIDTH } from '../../../shared/helpers/dialog-width';
import { ClosuresPanel } from '../components/closures-panel/closures-panel';
import { OverridePanel } from '../components/override-panel/override-panel';
import { StaffService } from '../services/staff.service';
import {
	Closure,
	ClosurePayload,
	ClosureQuery,
	Lane,
	OverridePayload,
	SlotQuery,
	StaffBooking,
	StaffResult,
} from '../types/staff';

const FAILED = 'That did not work. Nothing was changed.';
const LIST_FAILED = 'The closures list could not be loaded. Reload before closing a room.';

const newLane = (): Lane => ({ pending: signal(0), error: signal('') });

/** The answer of a staff action in words: how many were cancelled and what is left for tonight. */
function outcome(lead: string, result: StaffResult): string {
	const left = result.events_left
		? ` ${result.events_left} calendar event(s) will be removed tonight.`
		: '';
	return `${lead} ${result.cancelled} booking(s) cancelled and the students told.${left}`;
}

/** For staff only (the route guard hides it, the server refuses everyone else). Holds the panels' state. */
@Component({
	providers: [StaffService],
	imports: [AppHeader, ClosuresPanel, OverridePanel],
	selector: 'app-staff-page',
	templateUrl: './staff-page.html',
	styleUrl: './staff-page.css',
})
export class StaffPage {
	private readonly api = inject(StaffService);
	private readonly dialog = inject(MatDialog);
	private readonly closureLane = newLane();
	private readonly overrideLane = newLane();
	private readonly closureList = rxResource({ stream: () => this.api.closures() });
	/** Only reads are cancelled when the form changes: a close or take already sent must report back. */
	private previewCall: Subscription | null = null;
	private checkCall: Subscription | null = null;
	readonly closures = computed<Closure[]>(() => this.closureList.value() ?? []);
	/** Null until previewed: the close button needs a preview of exactly these dates. */
	readonly affected = signal<StaffBooking[] | null>(null);
	/** Null until checked: the take button needs a check of exactly this slot. */
	readonly holders = signal<StaffBooking[] | null>(null);
	readonly closureBusy = computed(() => this.closureLane.pending() > 0);
	readonly overrideBusy = computed(() => this.overrideLane.pending() > 0);
	readonly closureMessage = signal('');
	readonly overrideMessage = signal('');
	readonly closureError = computed(
		() => this.closureLane.error() || (this.closureList.error() ? LIST_FAILED : ''),
	);
	readonly overrideError = this.overrideLane.error.asReadonly();

	forgetPreview(): void {
		this.previewCall?.unsubscribe();
		this.affected.set(null);
		this.closureMessage.set('');
		this.closureLane.error.set('');
	}

	forgetCheck(): void {
		this.checkCall?.unsubscribe();
		this.holders.set(null);
		this.overrideMessage.set('');
		this.overrideLane.error.set('');
	}

	preview(query: ClosureQuery): void {
		this.previewCall?.unsubscribe();
		this.previewCall = this.run(
			this.closureLane,
			this.api.preview(query.room, query.start, query.end),
			(rows) => this.affected.set(rows),
		);
	}

	close(payload: ClosurePayload): void {
		this.run(this.closureLane, this.api.createClosure(payload), (result) => {
			this.affected.set(null);
			this.closureMessage.set(outcome('Room closed.', result));
			this.closureList.reload();
		});
	}

	askToReopen(closure: Closure): void {
		this.dialog
			.open<ConfirmDialog, unknown, boolean>(ConfirmDialog, {
				width: DIALOG_WIDTH,
				data: {
					title: 'Reopen this room?',
					message:
						`Room ${closure.room_number} reopens for ${closure.start_date} to ${closure.end_date}. ` +
						'Cancelled bookings stay cancelled.',
					confirmLabel: 'Reopen',
					cancelLabel: 'Keep closed',
				},
			})
			.afterClosed()
			.subscribe((confirmed) => {
				if (confirmed) {
					this.run(
						this.closureLane,
						this.api.deleteClosure(closure.id),
						() => this.closureList.reload(),
					);
				}
			});
	}

	check(query: SlotQuery): void {
		this.checkCall?.unsubscribe();
		this.checkCall = this.run(
			this.overrideLane,
			this.api.holder(query.room, query.startTime),
			(rows) => this.holders.set(rows),
		);
	}

	take(payload: OverridePayload): void {
		this.run(this.overrideLane, this.api.override(payload), (result) => {
			this.holders.set(null);
			this.overrideMessage.set(outcome('The slot is yours.', result));
		});
	}

	private run<T>(lane: Lane, request: Observable<T>, done: (value: T) => void): Subscription {
		lane.pending.update((count) => count + 1);
		lane.error.set('');
		return request
			.pipe(finalize(() => lane.pending.update((count) => count - 1)))
			.subscribe({
				next: done,
				error: (failure) => lane.error.set(serverDetail(failure) ?? FAILED),
			});
	}
}
