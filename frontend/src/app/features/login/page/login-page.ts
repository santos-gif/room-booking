import { Component, effect, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { AuthenticatedUser } from '../../../core/types/auth';
import { SigninGoogleBtn } from '../components/signin-google-btn/signin-google-btn';
import { LoginService } from '../service/login.service';

@Component({
	providers: [LoginService],
	imports: [SigninGoogleBtn],
	selector: 'app-login-page',
	styleUrl: './login-page.css',
	templateUrl: './login-page.html',
})
export class LoginPage {
	public readonly loginService = inject(LoginService);
	private readonly router = inject(Router);

	private readonly currentUser = toSignal<AuthenticatedUser | null>(this.loginService.me(), {
		initialValue: null,
	});
	private readonly deniedEffect = effect(() => {
		const reason = this.loginService.deniedReason();
		if (reason) {
			void this.router.navigate(['/access-denied'], {
				queryParams: { reason },
				replaceUrl: true,
			});
		}
	});
	private readonly redirectEffect = effect(() => {
		const user = this.currentUser();
		// A refused sign-in shows Access denied even when an older session is still cached.
		if (user && !this.loginService.deniedReason()) {
			void this.router.navigate([
				user.onboarding_complete ? '/my-bookings' : '/onboarding',
			]);
		}
	});
}
