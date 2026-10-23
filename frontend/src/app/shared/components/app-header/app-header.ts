import { Component, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/services/auth-service';
import { NavigationLock } from '../../../core/services/navigation-lock';
import { ConfirmDialog } from '../confirm-dialog/confirm-dialog';

@Component({
	imports: [RouterLink, RouterLinkActive],
	selector: 'app-header',
	styleUrl: './app-header.css',
	templateUrl: './app-header.html',
})
export class AppHeader {
	private readonly auth = inject(AuthService);
	private readonly dialog = inject(MatDialog);
	/** Locked while a booking is being saved: the links look and act disabled. */
	readonly lock = inject(NavigationLock).locked;

	/** Asks first: one stray tap on the phone must not end the session. */
	logout(): void {
		this.dialog
			.open<ConfirmDialog, unknown, boolean>(ConfirmDialog, {
				width: '400px',
				data: {
					title: 'Sign out?',
					message: 'You will need to sign in with Google again to book or manage rooms.',
					confirmLabel: 'Sign out',
					cancelLabel: 'Stay signed in',
				},
			})
			.afterClosed()
			.subscribe((confirmed) => {
				if (confirmed) {
					this.auth.logout().subscribe();
				}
			});
	}
}
