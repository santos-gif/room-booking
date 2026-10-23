/**
 * The AuthService is special as it implements the logic beyond simple endpoint calling
 * as the endpoints themselves are only reached out once or could only be used by one specific class or interceptor
 * implementing the logic within the service is recommended for this case
 */
import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { catchError, finalize, Observable, of, shareReplay, tap, throwError, timeout } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthenticatedUser, Major } from '../types/auth';

const LOGOUT_TIMEOUT_MS = 8_000;

@Injectable({ providedIn: 'root' })
export class AuthService {
	private readonly http = inject(HttpClient);

	login(): void {
		window.location.assign(`${environment.apiUrl}/google-auth/login`);
	}

	// The route guard asks for the user on every navigation; each ask used to be a round trip to a
	// serverless backend. Keep one answer per session instead (a failed request is not cached).
	private user$: Observable<AuthenticatedUser> | null = null;
	// Several requests can get 401 at once; they must share ONE refresh call (the refresh token rotates).
	private refreshing$: Observable<unknown> | null = null;

	me(): Observable<AuthenticatedUser> {
		this.user$ ??= this.http
			.get<AuthenticatedUser>(`${environment.apiUrl}/auth/me`)
			.pipe(shareReplay({ bufferSize: 1, refCount: false }));
		return this.user$;
	}

	saveOnboarding(nim: number, major: Major): Observable<AuthenticatedUser> {
		return this.http
			.post<AuthenticatedUser>(`${environment.apiUrl}/auth/onboarding`, {
				nim,
				major,
			})
			.pipe(tap((user) => (this.user$ = of(user))));
	}

	refresh(): Observable<unknown> {
		this.refreshing$ ??= this.http.post(`${environment.apiUrl}/auth/refresh`, {}).pipe(
			catchError((error: unknown) => {
				// The session is gone: the next navigation must ask the server again.
				this.user$ = null;
				return throwError(() => error);
			}),
			finalize(() => (this.refreshing$ = null)),
			shareReplay({ bufferSize: 1, refCount: false }),
		);
		return this.refreshing$;
	}

	logout(): Observable<unknown> {
		return this.http.post(`${environment.apiUrl}/auth/logout`, {}).pipe(
			// A slow server must not leave the button hanging: the cookies are cleared server-side or not at all.
			timeout(LOGOUT_TIMEOUT_MS),
			catchError(() => of(null)),
			tap(() => {
				window.location.assign('/');
			}),
		);
	}
}
