import { DatePipe } from '@angular/common';
import { Component, computed, input, output, signal, WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { OverridePayload, SlotQuery, StaffBooking } from '../../types/staff';

/** The one-hour slots a room offers: 08:00 to 16:00 (the last one ends at 17:00). */
const HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16];

/** The take-a-slot form and what the page answers; it never calls a service, the page does. */
@Component({
	imports: [DatePipe, FormsModule],
	selector: 'app-override-panel',
	templateUrl: './override-panel.html',
})
export class OverridePanel {
	/** Null until checked: the take button needs a check of exactly this slot. */
	readonly holders = input<StaffBooking[] | null>(null);
	readonly busy = input(false);
	readonly message = input('');
	readonly error = input('');
	/** Any change to the slot: the page forgets the check. */
	readonly edited = output<void>();
	readonly checkRequested = output<SlotQuery>();
	readonly takeRequested = output<OverridePayload>();
	readonly hours = HOURS;
	readonly room = signal<1 | 2>(1);
	readonly day = signal('');
	readonly hour = signal(9);
	readonly reason = signal('');
	readonly ready = computed(() => !!this.day());
	private readonly startTime = computed(
		() => `${this.day()}T${String(this.hour()).padStart(2, '0')}:00:00+07:00`,
	);

	edit<T>(target: WritableSignal<T>, value: T): void {
		target.set(value);
		this.edited.emit();
	}

	check(): void {
		this.checkRequested.emit({ room: this.room(), startTime: this.startTime() });
	}

	take(): void {
		this.takeRequested.emit({
			room_number: this.room(),
			start_time: this.startTime(),
			reason: this.reason().trim(),
		});
	}
}
