import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import { jakartaDate, jakartaToday } from '../../../../shared/helpers/jakarta-today';

const DAY_MS = 86_400_000;
/** Same limit as the server (slots.MAX_ADVANCE). */
const MAX_DAYS_AHEAD = 90;

/** Date picker and room switch. Owns no state: the page passes values in and hears changes out. */
@Component({
	selector: 'app-booking-controls',
	imports: [DatePipe],
	templateUrl: './booking-controls.html',
	styleUrl: './booking-controls.css',
})
export class BookingControls {
	readonly date = input.required<string>();
	readonly room = input.required<1 | 2>();
	/** True while availability loads or a booking is saving: nothing here may be pressed then. */
	readonly disabled = input(false);
	readonly dateChange = output<string>();
	readonly roomChange = output<1 | 2>();
	protected readonly rooms = [1, 2] as const;
	/** The bookable window: today through MAX_DAYS_AHEAD (Jakarta). */
	protected readonly minDate = jakartaToday();
	protected readonly maxDate = jakartaDate(new Date(Date.now() + MAX_DAYS_AHEAD * DAY_MS));

	protected pick(picker: HTMLInputElement): void {
		if (picker.value) {
			this.dateChange.emit(picker.value);
		}
	}

	// Desktop Chrome only opens the calendar from its small icon; this makes the whole field open it.
	protected openPicker(picker: HTMLInputElement): void {
		try {
			picker.showPicker();
		} catch {
			// Not supported or blocked: the native control still works when tapped.
		}
	}
}
