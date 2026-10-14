import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
	Availability,
	BookingAppointment,
	BookingPayload,
} from '../types/booking-form';

@Injectable()
export class BookingFormService {
	private readonly http = inject(HttpClient);
	private readonly baseUrl = `${environment.apiUrl}/appointments`;

	availability(
		date: string,
		roomNumber: 1 | 2,
	): Observable<Availability> {
		const params = new HttpParams()
			.set('date', date)
			.set('room_number', roomNumber);
		return this.http.get<Availability>(`${this.baseUrl}/availability`, {
			params,
		});
	}

	book(payload: BookingPayload): Observable<BookingAppointment> {
		return this.http.post<BookingAppointment>(`${this.baseUrl}/`, payload);
	}
}
