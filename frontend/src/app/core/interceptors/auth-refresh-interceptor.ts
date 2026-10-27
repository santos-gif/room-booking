import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { SessionExpiredDialog } from '../../shared/components/session-expired-dialog/session-expired-dialog';
import { DIALOG_WIDTH } from '../../shared/helpers/dialog-width';
import { AuthService } from '../services/auth-service';
import { hasCookie } from '../utils/cookies';

// The backend sets csrf_token with the same 30-day lifetime as the refresh cookie and clears them
// together, so no csrf_token means nobody is signed in and a refresh could only fail.
const hasSession = (): boolean => hasCookie('csrf_token');

// These ask "who am I" or end the session; a 401 from them is an answer, not an interrupted student.
const isSessionProbe = (url: string): boolean =>
	['auth/me', 'auth/refresh', 'auth/logout'].some((path) => url.includes(path));

/** Tells the student their session is over and takes them to sign-in once they confirm. */
function expireSession(dialog: MatDialog, router: Router): void {
	const onSignInPage = router.url.split('?')[0] === '/';
	if (onSignInPage || dialog.getDialogById('session-expired')) {
		return;
	}
	dialog.open(SessionExpiredDialog, {
		id: 'session-expired',
		width: DIALOG_WIDTH,
		disableClose: true,
	})
		.afterClosed()
		.subscribe(() => void router.navigateByUrl('/'));
}

export const authRefreshInterceptor: HttpInterceptorFn = (req, next) => {
	const authService = inject(AuthService);
	const dialog = inject(MatDialog);
	const router = inject(Router);
	return next(req).pipe(
		catchError((error: HttpErrorResponse) => {
			// Signed out elsewhere (another tab): the cookies are gone, so there is nothing to refresh.
			if (error.status === 401 && !hasSession() && !isSessionProbe(req.url)) {
				expireSession(dialog, router);
			}
			if (
				error.status === 401 &&
				hasSession() &&
				!isSessionProbe(req.url) &&
				!req.headers.has('X-Retry-Attempt')
			) {
				return authService.refresh().pipe(
					catchError((refreshError) => {
						// The session cannot be renewed: tell the student instead of a page of failing requests.
						expireSession(dialog, router);
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
