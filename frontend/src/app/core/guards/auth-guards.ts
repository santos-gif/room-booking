import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth-service';
import { hasCookie } from '../utils/cookies';

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
		catchError((error: { status?: number }) => {
			const status = error?.status;
			// A 401 while the csrf cookie still exists means a session existed but could not be renewed.
			const expired = status === 401 && hasCookie('csrf_token');
			const target =
				status === 401 || status === 404
					? expired
						? '/?auth_error=session_expired'
						: '/'
					: '/?auth_error=server_unavailable';
			return of(router.parseUrl(target));
		}),
	);
};
