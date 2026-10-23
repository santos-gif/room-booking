import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth-service';
import { hasCookie } from '../utils/cookies';

// The backend sets csrf_token with the same 30-day lifetime as the refresh cookie and clears them
// together, so no csrf_token means nobody is signed in and a refresh could only fail.
const hasSession = (): boolean => hasCookie('csrf_token');

export const authRefreshInterceptor: HttpInterceptorFn = (req, next) => {
	const authService = inject(AuthService);
	const router = inject(Router);
	return next(req).pipe(
		catchError((error: HttpErrorResponse) => {
			if (
				error.status === 401 &&
				hasSession() &&
				!req.url.includes('auth/refresh') &&
				!req.url.includes('auth/logout') &&
				!req.headers.has('X-Retry-Attempt')
			) {
				return authService.refresh().pipe(
					catchError((refreshError) => {
						// The session cannot be renewed: back to sign-in instead of a page of failing requests.
						if (router.url.split('?')[0] !== '/') {
							void router.navigateByUrl(
								'/?auth_error=session_expired',
							);
						}
						return throwError(() => refreshError);
					}),
					// Outside the catch above: a retry that fails (409 slot taken, 500) is that request's
					// own error, not an expired session.
					switchMap(() =>
						next(
							req.clone({
								headers: req.headers.set(
									'X-Retry-Attempt',
									'1',
								),
							}),
						),
					),
				);
			}
			return throwError(() => error);
		}),
	);
};
