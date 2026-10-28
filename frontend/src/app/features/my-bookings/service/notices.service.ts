import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { environment } from '../../../../environments/environment';

export interface Notice {
	id: string;
	message: string;
	created_at: string;
}

/** Messages for a student whose booking staff cancelled; shown on My bookings until dismissed. */
@Injectable({ providedIn: 'root' })
export class NoticesService {
	private readonly http = inject(HttpClient);
	private readonly baseUrl = `${environment.apiUrl}/appointments/notices`;
	readonly notices = signal<Notice[]>([]);

	load(): void {
		// A notice is a courtesy: failing to load it must never break the page.
		this.http.get<Notice[]>(this.baseUrl).subscribe({
			next: (list) => this.notices.set(list),
			error: () => undefined,
		});
	}

	dismiss(id: string): void {
		this.notices.update((list) => list.filter((notice) => notice.id !== id));
		this.http
			.post<void>(`${this.baseUrl}/${encodeURIComponent(id)}/seen`, {})
			.subscribe({
				error: () => this.load(),
			});
	}
}
