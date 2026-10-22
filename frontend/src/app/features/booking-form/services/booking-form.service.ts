import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Availability, BookingAppointment, BookingPayload } from '../types/booking-form';

@Injectable()
export class BookingFormService {
	private readonly http = inject(HttpClient);
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
		return this.http.get<BookingAppointment[]>(`${this.baseUrl}/`);
	}

	book(payload: BookingPayload): Observable<BookingAppointment> {
		return this.http.post<BookingAppointment>(`${this.baseUrl}/`, payload);
	}

	reschedule(id: string, payload: BookingPayload): Observable<BookingAppointment> {
		return this.http.post<BookingAppointment>(
			`${this.baseUrl}/${id}/reschedule`,
			payload,
		);
	}
}
