import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';

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

	// Desktop Chrome only opens the calendar from its small icon; this makes the whole field open it.
	protected openPicker(picker: HTMLInputElement): void {
		try {
			picker.showPicker();
		} catch {
			// Not supported or blocked: the native control still works when tapped.
		}
	}
}
