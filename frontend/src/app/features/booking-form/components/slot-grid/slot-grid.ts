import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import { AvailableSlot } from '../../types/booking-form';

/** One-hour time buttons for the chosen day and room. Nothing is shown while availability loads. */
@Component({
	selector: 'app-slot-grid',
	imports: [DatePipe],
	templateUrl: './slot-grid.html',
	styleUrl: './slot-grid.css',
})
export class SlotGrid {
	readonly slots = input.required<AvailableSlot[]>();
	readonly selected = input<AvailableSlot | null>(null);
	/** Start of the booking being updated, so its own time can be outlined. */
	readonly current = input<string | null>(null);
	readonly loading = input(false);
	readonly disabled = input(false);
	readonly pick = output<AvailableSlot>();

	// Compared as instants: the API sends +07:00 and Z forms of the same time.
	protected isCurrent(slot: AvailableSlot): boolean {
		const current = this.current();
		return (
			current !== null &&
			new Date(current).getTime() === new Date(slot.start_time).getTime()
		);
	}
}
