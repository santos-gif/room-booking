import { computed, inject, Injectable, signal } from '@angular/core';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser } from '../../../core/types/auth';
import { catchError, Observable, of } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';

@Injectable()
export class LoginService {
	private readonly authService = inject(AuthService);

	private readonly sessionError = signal('');
	private readonly route = inject(ActivatedRoute);


	private readonly queryParams = toSignal(
		this.route.queryParamMap,
		{ initialValue: this.route.snapshot.queryParamMap },
	);

	readonly errorMessage = computed(
		() => this.sessionError() || this.authError(),
	);
	login(): void {
		this.authService.login();
	}

	me(): Observable<AuthenticatedUser | null> {
		return this.authService.me().pipe(
			catchError((error: unknown) => {
				if (
					!(error instanceof HttpErrorResponse)
					|| (error.status !== 401 && error.status !== 404)
				) {
					this.sessionError.set(
						'Unable to check your session. Please try again.',
					);
				}
				return of(null);
			}),
		);
	}
	private authError(): string {
		const errors: Record<string, string> = {
			google_access_denied: 'Google sign-in was cancelled.',
			google_exchange_failed: 'Google sign-in failed. Please try again.',
			calendar_consent_required:
				'Grant Google Calendar access to finish connecting your account.',
			verified_email_required: 'Sign in with a verified Google account.',
			university_email_required:
				'Use your @student.pradita.ac.id or @pradita.ac.id account.',
			account_link_required:
				'Contact an administrator to securely link your existing booking profile.',
		};
		const code = this.queryParams().get('auth_error') ?? '';
		return errors[code] ?? '';
	}
}
