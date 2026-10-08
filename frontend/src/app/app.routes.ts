import { Routes } from '@angular/router';
import { authenticatedGuard } from './core/guards/auth-guards';
import { BookingFormPage } from './features/booking-form/pages/booking-form-page/booking-form-page';
import { LoginPage } from './features/login/page/login-page';
import { OnboardingPage } from './features/onboarding/page/onboarding-page';

export const routes: Routes = [
	{ path: '', component: LoginPage, pathMatch: 'full' },
	{
		path: 'onboarding',
		component: OnboardingPage,
		canActivate: [authenticatedGuard],
	},
	{
		path: 'booking-form',
		component: BookingFormPage,
		canActivate: [authenticatedGuard],
	},
	{ path: '**', redirectTo: '' },
];
