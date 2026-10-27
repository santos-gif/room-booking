import { toSignal } from '@angular/core/rxjs-interop';
import { computed, inject, Injectable } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { catchError, Observable, of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser } from '../../../core/types/auth';

/** Messages for the fixed codes the backend puts in `?auth_error=`. Nothing else is ever shown. */
const AUTH_ERRORS: Record<string, string> = {
	google_access_denied: 'Google sign-in was cancelled.',
	google_exchange_failed: 'Google sign-in failed. Please try again.',
	session_expired: 'Your session expired. Please sign in again.',
	server_unavailable: 'The server is not reachable right now. Please try again in a moment.',
};

/** Refusals: they open the Access denied page instead of a message on the form. */
const DENIED_CODES = [
	'university_email_required',
	'verified_email_required',
	'account_link_required',
];

@Injectable()
export class LoginService {
	private readonly authService = inject(AuthService);
	private readonly route = inject(ActivatedRoute);

	private readonly queryParams = toSignal(this.route.queryParamMap, {
		initialValue: this.route.snapshot.queryParamMap,
	});
	private readonly authErrorCode = computed(() => this.queryParams().get('auth_error') ?? '');

	// hasOwn: ?auth_error=constructor must not find Object's own members.
	readonly errorMessage = computed(() => {
		const code = this.authErrorCode();
		return Object.hasOwn(AUTH_ERRORS, code) ? AUTH_ERRORS[code] : '';
	});

	readonly deniedReason = computed(() => {
		const code = this.authErrorCode();
		return DENIED_CODES.includes(code) ? code : '';
	});

	login(): void {
		this.authService.login();
	}

	/** The login page must always render: any failure (signed out, server down) just means "no user". */
	me(): Observable<AuthenticatedUser | null> {
		return this.authService.me().pipe(catchError(() => of(null)));
	}
}
