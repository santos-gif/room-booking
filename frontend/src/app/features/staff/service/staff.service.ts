import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { BookingsStore } from '../../../core/services/bookings-store';
import {
	Closure,
	ClosurePayload,
	OverridePayload,
	StaffBooking,
	StaffResult,
} from '../types/staff';

/** The staff routes. Every one answers 403 to a student: this page is for looks, the server decides. */
@Injectable()
export class StaffService {
	private readonly http = inject(HttpClient);
	private readonly bookings = inject(BookingsStore);
	private readonly baseUrl = `${environment.apiUrl}/staff`;

	closures(): Observable<Closure[]> {
		return this.http.get<Closure[]>(`${this.baseUrl}/closures`);
	}

	/** Who a closure of these dates would cancel (nothing is changed). */
	preview(room: 1 | 2, start: string, end: string): Observable<StaffBooking[]> {
		const params = new HttpParams()
			.set('room_number', room)
			.set('start_date', start)
			.set('end_date', end);
		return this.http.get<StaffBooking[]>(`${this.baseUrl}/closures/preview`, {
			params,
		});
	}

	createClosure(payload: ClosurePayload): Observable<StaffResult> {
		this.bookings.invalidate();
		return this.http.post<StaffResult>(`${this.baseUrl}/closures`, payload);
	}

	deleteClosure(id: string): Observable<void> {
		return this.http.delete<void>(`${this.baseUrl}/closures/${encodeURIComponent(id)}`);
	}

	/** Who holds a slot right now (an empty list means it is free). */
	holder(room: 1 | 2, startTime: string): Observable<StaffBooking[]> {
		const params = new HttpParams()
			.set('room_number', room)
			.set('start_time', startTime);
		return this.http.get<StaffBooking[]>(`${this.baseUrl}/slot`, { params });
	}

	override(payload: OverridePayload): Observable<StaffResult> {
		this.bookings.invalidate();
		return this.http.post<StaffResult>(`${this.baseUrl}/override`, payload);
	}
}
