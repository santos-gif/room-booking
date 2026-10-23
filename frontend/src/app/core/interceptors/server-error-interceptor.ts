import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { catchError, throwError } from 'rxjs';
import { ErrorDialog } from '../../shared/components/error-dialog/error-dialog';
import { DIALOG_WIDTH } from '../../shared/helpers/dialog-width';

export const serverErrorInterceptor: HttpInterceptorFn = (req, next) => {
	const dialog = inject(MatDialog);

	return next(req).pipe(
		catchError((error: HttpErrorResponse) => {
			// One dialog at a time, and none for the availability poll (the page shows its own message).
			// Saving or cancelling a booking shows its own message on the page: a second dialog would stack.
			const savingBooking =
				req.method !== 'GET' && req.url.includes('/appointments');
			const quiet =
				req.url.includes('/availability') ||
				savingBooking ||
				dialog.openDialogs.length > 0;
			if ((error.status === 0 || error.status >= 500) && !quiet) {
				const message =
					error.status === 0
						? 'Cannot connect to the server. Check your internet connection.'
						: 'The server is experiencing issues. Please try again in a moment.';
				dialog.open(ErrorDialog, {
					data: { errorMessage: message },
					width: DIALOG_WIDTH,
				});
			}
			return throwError(() => error);
		}),
	);
};
