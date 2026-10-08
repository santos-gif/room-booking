import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth-service';

export const authenticatedGuard: CanActivateFn = (_route, state) => {
	const auth = inject(AuthService);
	const router = inject(Router);
	return auth.me().pipe(
		map((user) => {
			if (!user.onboarding_complete && state.url !== '/onboarding') {
				return router.parseUrl('/onboarding');
			}
			if (user.onboarding_complete && state.url === '/onboarding') {
				return router.parseUrl('/booking-form');
			}
			return true;
		}),
		catchError(() => of(router.parseUrl('/'))),
	);
};
