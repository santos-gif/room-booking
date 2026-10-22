import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth-service';

export const authenticatedGuard: CanActivateFn = (_route, state) => {
	const auth = inject(AuthService);
	const router = inject(Router);
	return auth.me().pipe(
		map((user) => {
			const path = state.url.split('?')[0];
			if (!user.onboarding_complete && path !== '/onboarding') {
				return router.parseUrl('/onboarding');
			}
			if (user.onboarding_complete && path === '/onboarding') {
				return router.parseUrl('/my-bookings');
			}
			return true;
		}),
		// 401/404 mean "not signed in". Anything else (server down, offline) is not the student's fault:
		// say so on the login page instead of pretending they are signed out.
		catchError((error: { status?: number }) =>
			of(
				router.parseUrl(
					error?.status === 401 || error?.status === 404
						? '/'
						: '/?auth_error=server_unavailable',
				),
			),
		),
	);
};
