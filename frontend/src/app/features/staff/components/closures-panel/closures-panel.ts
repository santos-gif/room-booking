import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal, WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { serverDetail } from '../../../../core/utils/api-failure';
import { ConfirmDialog } from '../../../../shared/components/confirm-dialog/confirm-dialog';
import { DIALOG_WIDTH } from '../../../../shared/helpers/dialog-width';
import { StaffService } from '../../service/staff.service';
import { Closure, StaffBooking } from '../../types/staff';

/** Close a room for a range of dates (past dates too): preview who is affected, then close it. */
@Component({
	imports: [DatePipe, FormsModule],
	selector: 'app-closures-panel',
	templateUrl: './closures-panel.html',
})
export class ClosuresPanel {
	private readonly api = inject(StaffService);
	private readonly dialog = inject(MatDialog);
	readonly room = signal<1 | 2>(1);
	readonly start = signal('');
	readonly end = signal('');
	readonly reason = signal('');
	readonly closures = signal<Closure[]>([]);
	/** Null until previewed: the close button needs a preview of exactly these dates. */
	readonly affected = signal<StaffBooking[] | null>(null);
	readonly busy = signal(false);
	readonly message = signal('');
	readonly error = signal('');
	readonly ready = computed(
		() =>
			!!this.start() &&
			!!this.end() &&
			this.end() >= this.start() &&
			!!this.reason().trim(),
	);

	constructor() {
		this.load();
	}

	/** Any change to the form invalidates the preview. */
	edit<T>(target: WritableSignal<T>, value: T): void {
		target.set(value);
		this.affected.set(null);
		this.message.set('');
	}

	preview(): void {
		this.run(this.api.preview(this.room(), this.start(), this.end()), (rows) =>
			this.affected.set(rows),
		);
	}

	close(): void {
		const payload = {
			room_number: this.room(),
			start_date: this.start(),
			end_date: this.end(),
			reason: this.reason().trim(),
		};
		this.run(this.api.createClosure(payload), (result) => {
			this.affected.set(null);
			this.message.set(
				`Room closed. ${result.cancelled} booking(s) cancelled and the students told.` +
					(result.events_left
						? ` ${result.events_left} calendar event(s) will be removed tonight.`
						: ''),
			);
			this.load();
		});
	}

	remove(closure: Closure): void {
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
					this.run(this.api.deleteClosure(closure.id), () =>
						this.load(),
					);
				}
			});
	}

	private load(): void {
		this.api.closures().subscribe({
			next: (list) => this.closures.set(list),
			error: () => undefined,
		});
	}

	private run<T>(request: Observable<T>, done: (value: T) => void): void {
		this.busy.set(true);
		this.error.set('');
		request.subscribe({
			next: (value) => {
				this.busy.set(false);
				done(value);
			},
			error: (failure) => {
				this.busy.set(false);
				this.error.set(
					serverDetail(failure) ??
						'That did not work. Nothing was changed.',
				);
			},
		});
	}
}
