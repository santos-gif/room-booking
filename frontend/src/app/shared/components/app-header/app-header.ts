import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/services/auth-service';

@Component({
	imports: [RouterLink, RouterLinkActive],
	selector: 'app-header',
	styleUrl: './app-header.css',
	templateUrl: './app-header.html',
})
export class AppHeader {
	private readonly auth = inject(AuthService);

	logout(): void {
		this.auth.logout().subscribe();
	}
}
