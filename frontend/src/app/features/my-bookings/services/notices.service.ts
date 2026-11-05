import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Notice } from '../types/notice';

/** The notices routes: what staff cancelled, and "seen". The page keeps the list. */
@Injectable()
export class NoticesService {
	private readonly http = inject(HttpClient);
	private readonly baseUrl = `${environment.apiUrl}/appointments/notices`;

	list(): Observable<Notice[]> {
		return this.http.get<Notice[]>(this.baseUrl);
	}

	dismiss(id: string): Observable<void> {
		return this.http.post<void>(`${this.baseUrl}/${encodeURIComponent(id)}/seen`, {});
	}
}
