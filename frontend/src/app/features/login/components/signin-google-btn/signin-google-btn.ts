import { Component, inject } from '@angular/core';
import { LoginService } from '../../service/login.service';

@Component({
	imports: [],
	providers: [LoginService],
	selector: 'app-signin-google-btn',
	styleUrl: './signin-google-btn.css',
	templateUrl: './signin-google-btn.html',
})
export class SigninGoogleBtn {
	private readonly loginService = inject(LoginService);

	signIn(): void {
		this.loginService.login();
	}
}
