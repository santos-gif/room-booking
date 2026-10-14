import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { catchError, Observable, switchMap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthenticatedUser, Major } from '../types/auth';

@Injectable({ providedIn: 'root' })
export class AuthService {
	private readonly http = inject(HttpClient);

	login = (): void => {
		window.location.assign(`${environment.apiUrl}/google-auth/login`);
	}

	me(): Observable<AuthenticatedUser> {
		const endpoint = `${environment.apiUrl}/auth/me`;
		return this.http.get<AuthenticatedUser>(endpoint).pipe(
			catchError((error: unknown) => {
				if (
					typeof error !== 'object'
					|| error === null
					|| !('status' in error)
					|| error.status !== 401
				) {
					return throwError(() => error);
				}
				return this.http
					.post(`${environment.apiUrl}/auth/refresh`, {})
					.pipe(switchMap(() => this.http.get<AuthenticatedUser>(endpoint)));
			}),
		);
	}

	saveOnboarding(nim: number, major: Major): Observable<AuthenticatedUser> {
		return this.http.post<AuthenticatedUser>(
			`${environment.apiUrl}/auth/onboarding`,
			{ nim, major },
		);
	}
}
