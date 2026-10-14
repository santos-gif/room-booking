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


	private readonly currentUser = toSignal<AuthenticatedUser | null>(
		this.loginService.me(),
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
}
