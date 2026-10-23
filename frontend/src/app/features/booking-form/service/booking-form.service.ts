import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { finalize, Observable, timeout } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { BookingsStore } from '../../../core/services/bookings-store';
import { Availability, BookingAppointment, BookingPayload } from '../types/booking-form';

/** A save that hangs must fail, or the navbar lock would never release. */
const SAVE_TIMEOUT_MS = 30_000;

@Injectable()
export class BookingFormService {
	private readonly http = inject(HttpClient);
	private readonly bookings = inject(BookingsStore);
	private readonly baseUrl = `${environment.apiUrl}/appointments`;

	/** `excludeId` is the booking being updated: it must not count against the 3-booking limit or its own slot. */
	availability(
		date: string,
		roomNumber: 1 | 2,
		excludeId?: string,
	): Observable<Availability> {
		let params = new HttpParams().set('date', date).set('room_number', roomNumber);
		if (excludeId) {
			params = params.set('exclude_appointment_id', excludeId);
		}
		return this.http.get<Availability>(`${this.baseUrl}/availability`, { params });
	}

	/** The student's own upcoming bookings; update mode uses it to find the booking being moved. */
	mine(): Observable<BookingAppointment[]> {
		// verify=true also checks Google Calendar, so a booking whose event was deleted there is "gone".
		const params = new HttpParams().set('verify', 'true');
		return this.http.get<BookingAppointment[]>(`${this.baseUrl}/`, { params });
	}

	// Both may change the student's list (even when the answer is lost: the server may have saved it).
	book(payload: BookingPayload): Observable<BookingAppointment> {
		return this.http.post<BookingAppointment>(`${this.baseUrl}/`, payload).pipe(
			timeout(SAVE_TIMEOUT_MS),
			finalize(() => this.bookings.invalidate()),
		);
	}

	reschedule(id: string, payload: BookingPayload): Observable<BookingAppointment> {
		return this.http
			.post<BookingAppointment>(
				`${this.baseUrl}/${encodeURIComponent(id)}/reschedule`,
				payload,
			)
			.pipe(
				timeout(SAVE_TIMEOUT_MS),
				finalize(() => this.bookings.invalidate()),
			);
	}

	/** The shared bookings list is out of date (for example the booking being updated is gone). */
	invalidateBookings(): void {
		this.bookings.invalidate();
	}
}
