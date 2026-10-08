import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { catchError, of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser } from '../../../core/types/auth';
import { SigninGoogleBtn } from '../components/signin-google-btn/signin-google-btn';

@Component({
	imports: [SigninGoogleBtn],
	selector: 'app-login-page',
	styleUrl: './login-page.css',
	templateUrl: './login-page.html',
})
export class LoginPage {
	private readonly auth = inject(AuthService);
	private readonly router = inject(Router);
	private readonly route = inject(ActivatedRoute);
	private readonly queryParams = toSignal(
		this.route.queryParamMap,
		{ initialValue: this.route.snapshot.queryParamMap },
	);
	private readonly sessionError = signal('');
	readonly errorMessage = computed(
		() => this.sessionError() || this.authError(),
	);
	private readonly currentUser = toSignal<AuthenticatedUser | null>(
		this.auth.me().pipe(
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
		),
		{ initialValue: null },
	);
	private readonly redirectEffect = effect(() => {
		const user = this.currentUser();
		if (user) {
			void this.router.navigate([
				user.onboarding_complete ? '/booking-form' : '/onboarding',
			]);
		}
	});

	private authError(): string {
		const errors: Record<string, string> = {
			google_access_denied: 'Google sign-in was cancelled.',
			google_exchange_failed: 'Google sign-in failed. Please try again.',
			calendar_consent_required:
				'Grant Google Calendar access to finish connecting your account.',
			verified_email_required: 'Sign in with a verified Google account.',
			university_email_required:
				'Use your @student.pradita.ac.id or @pradita.ac.id account.',
		};
		const code = this.queryParams().get('auth_error') ?? '';
		return errors[code] ?? '';
	}
}
