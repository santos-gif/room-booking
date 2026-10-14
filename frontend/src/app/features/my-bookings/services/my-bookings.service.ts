import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Appointment } from '../types/my-bookings';

@Injectable()
export class MyBookingsService {
	private readonly http = inject(HttpClient);
	private readonly baseUrl = `${environment.apiUrl}/appointments`;

	list(): Observable<Appointment[]> {
		return this.http.get<Appointment[]>(`${this.baseUrl}/`);
	}

	cancel(id: string): Observable<void> {
		return this.http.delete<void>(`${this.baseUrl}/${id}`);
	}
}
