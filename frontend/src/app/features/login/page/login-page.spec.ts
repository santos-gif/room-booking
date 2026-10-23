import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { LoginService } from '../service/login.service';
import { LoginPage } from './login-page';

describe('LoginPage (who is sent where)', () => {
	function setup(options: { errorMessage?: string; deniedReason?: string }) {
		const service = {
			errorMessage: signal(options.errorMessage ?? ''),
			deniedReason: signal(options.deniedReason ?? ''),
			me: () => of({ onboarding_complete: true }),
			login: vi.fn(),
		};
		TestBed.configureTestingModule({
			providers: [provideRouter([])],
		}).overrideComponent(LoginPage, {
			set: { providers: [{ provide: LoginService, useValue: service }] },
		});
		const navigate = vi
			.spyOn(TestBed.inject(Router), 'navigate')
			.mockResolvedValue(true);
		TestBed.createComponent(LoginPage).detectChanges();
		TestBed.tick();
		return navigate;
	}

	it('sends a signed-in student straight to My bookings', () => {
		expect(setup({})).toHaveBeenCalledWith(['/my-bookings']);
	});

	it('keeps a sign-in error on screen even if an older session is still valid', () => {
		const navigate = setup({
			errorMessage:
				'Grant Google Calendar access to finish connecting your account.',
		});
		expect(navigate).not.toHaveBeenCalledWith(['/my-bookings']);
	});

	it('shows Access denied for a refused account, never My bookings', () => {
		const navigate = setup({ deniedReason: 'university_email_required' });
		expect(navigate).toHaveBeenCalledWith(['/access-denied'], expect.anything());
		expect(navigate).not.toHaveBeenCalledWith(['/my-bookings']);
	});
});
