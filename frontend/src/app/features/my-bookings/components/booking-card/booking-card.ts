import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import { Appointment } from '../../types/my-bookings';

/** One upcoming booking, shown in WIB. Updating and cancelling are the parent's job: this only reports clicks. */
@Component({
	selector: 'app-booking-card',
	imports: [DatePipe],
	templateUrl: './booking-card.html',
	styleUrl: './booking-card.css',
})
export class BookingCard {
	readonly appointment = input.required<Appointment>();
	readonly busy = input(false);
	readonly updateRequested = output<void>();
	readonly cancelRequested = output<void>();
}
