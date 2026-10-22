import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import { AvailableSlot } from '../../types/booking-form';

/** Side panel (bottom sheet on phones) that summarises the chosen slot before it is booked. */
@Component({
	selector: 'app-confirm-panel',
	imports: [DatePipe],
	templateUrl: './confirm-panel.html',
	styleUrl: './confirm-panel.css',
})
export class ConfirmPanel {
	readonly slot = input.required<AvailableSlot>();
	readonly room = input.required<1 | 2>();
	readonly updating = input(false);
	readonly submitting = input(false);
	readonly confirmed = output<void>();
	readonly dismissed = output<void>();
}
