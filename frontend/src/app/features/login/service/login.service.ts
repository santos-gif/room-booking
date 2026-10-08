import { inject, Injectable } from '@angular/core';
import { AuthService } from '../../../core/services/auth-service';

@Injectable({ providedIn: 'root' })
export class LoginService {
	private readonly authService = inject(AuthService);

	login(): void {
		this.authService.login();
	}
}
