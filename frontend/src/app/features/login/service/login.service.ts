import { computed, inject, Injectable, signal } from '@angular/core';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser } from '../../../core/types/auth';
import { catchError, Observable, of } from 'rxjs';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';

@Injectable()
export class LoginService {
	private readonly authService = inject(AuthService);
	private readonly route = inject(ActivatedRoute);

	private readonly queryParams = toSignal(this.route.queryParamMap, {
		initialValue: this.route.snapshot.queryParamMap,
	});

	readonly errorMessage = computed(() => this.authError());

	login(): void {
		this.authService.login();
	}

	/** The login page must always render: any failure (signed out, server down) just means "no user". */
	me(): Observable<AuthenticatedUser | null> {
		return this.authService.me().pipe(catchError(() => of(null)));
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
			session_expired: 'Your session expired. Please sign in again.',
			server_unavailable:
				'The server is not reachable right now. Please try again in a moment.',
		};
		const code = this.queryParams().get('auth_error') ?? '';
		return errors[code] ?? '';
	}
}
