import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal, WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiFailure, serverDetail } from '../../../../core/utils/api-failure';
import { StaffService } from '../../service/staff.service';
import { StaffBooking } from '../../types/staff';

/** The one-hour slots a room offers: 08:00 to 16:00 (the last one ends at 17:00). */
const HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16];

/** Take one slot for staff: see who holds it, then cancel them (they are told) and keep it. */
@Component({
	imports: [DatePipe, FormsModule],
	selector: 'app-override-panel',
	templateUrl: './override-panel.html',
})
export class OverridePanel {
	private readonly api = inject(StaffService);
	readonly hours = HOURS;
	readonly room = signal<1 | 2>(1);
	readonly day = signal('');
	readonly hour = signal(9);
	readonly reason = signal('');
	/** Null until checked: the take button needs a check of exactly this slot. */
	readonly holders = signal<StaffBooking[] | null>(null);
	readonly busy = signal(false);
	readonly message = signal('');
	readonly error = signal('');
	readonly ready = computed(() => !!this.day());
	private readonly startTime = computed(
		() => `${this.day()}T${String(this.hour()).padStart(2, '0')}:00:00+07:00`,
	);

	/** Any change to the form invalidates the check. */
	edit<T>(target: WritableSignal<T>, value: T): void {
		target.set(value);
		this.holders.set(null);
		this.message.set('');
	}

	check(): void {
		this.busy.set(true);
		this.error.set('');
		this.api.holder(this.room(), this.startTime()).subscribe({
			next: (rows) => {
				this.busy.set(false);
				this.holders.set(rows);
			},
			error: (failure) => this.fail(failure),
		});
	}

	take(): void {
		this.busy.set(true);
		this.error.set('');
		const payload = {
			room_number: this.room(),
			start_time: this.startTime(),
			reason: this.reason().trim(),
		};
		this.api.override(payload).subscribe({
			next: (result) => {
				this.busy.set(false);
				this.holders.set(null);
				this.message.set(
					`The slot is yours. ${result.cancelled} booking(s) cancelled and the students told.` +
						(result.events_left
							? ` ${result.events_left} calendar event(s) will be removed tonight.`
							: ''),
				);
			},
			error: (failure) => this.fail(failure),
		});
	}

	private fail(failure: ApiFailure): void {
		this.busy.set(false);
		this.error.set(serverDetail(failure) ?? 'That did not work. Nothing was changed.');
	}
}
