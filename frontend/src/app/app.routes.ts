import { Routes } from '@angular/router';
import { authenticatedGuard } from './core/guards/auth-guards';
import { unlessLocked } from './core/guards/leave-guard';

// Pages are lazy so the first paint only ships the login screen; app.config preloads the rest.
const onboarding = () =>
	import('./features/onboarding/page/onboarding-page').then((m) => m.OnboardingPage);

export const routes: Routes = [
	{
		path: '',
		pathMatch: 'full',
		loadComponent: () =>
			import('./features/login/page/login-page').then((m) => m.LoginPage),
	},
	{
		path: 'onboarding',
		loadComponent: onboarding,
		canActivate: [authenticatedGuard],
	},
	{
		path: 'profile',
		loadComponent: onboarding,
		data: { mode: 'edit' },
		canActivate: [authenticatedGuard],
	},
	{
		path: 'booking-form',
		loadComponent: () =>
			import('./features/booking-form/page/booking-form-page').then(
				(m) => m.BookingFormPage,
			),
		canActivate: [authenticatedGuard],
		canDeactivate: [unlessLocked],
	},
	{
		path: 'my-bookings',
		loadComponent: () =>
			import('./features/my-bookings/page/my-bookings-page').then(
				(m) => m.MyBookingsPage,
			),
		canActivate: [authenticatedGuard],
	},
	{
		path: 'access-denied',
		loadComponent: () =>
			import('./features/access-denied/page/access-denied-page').then(
				(m) => m.AccessDeniedPage,
			),
	},
	{ path: '**', redirectTo: '' },
];
