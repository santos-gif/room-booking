import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { OnboardingPage } from './onboarding-page';

describe('OnboardingPage', () => {
	function setup(save: () => unknown = () => of({ onboarding_complete: true })) {
		const saveOnboarding = vi.fn(save);
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{
					provide: AuthService,
					useValue: { saveOnboarding, me: () => of({}) },
				},
			],
		});
		const navigate = vi
			.spyOn(TestBed.inject(Router), 'navigate')
			.mockResolvedValue(true);
		const page = TestBed.createComponent(OnboardingPage).componentInstance;
		return { page, saveOnboarding, navigate };
	}

	it('saves through AuthService (which keeps the guards cache fresh) and goes to My bookings', () => {
		const { page, saveOnboarding, navigate } = setup();
		page.nim.set(2510101051);
		page.major.set('Information Technology');
		page.submit();
		expect(saveOnboarding).toHaveBeenCalledWith(2510101051, 'Information Technology');
		expect(navigate).toHaveBeenCalledWith(['/my-bookings']);
	});

	function submitWith(save: () => unknown) {
		const { page } = setup(save);
		page.nim.set(2510101051);
		page.major.set('Information Technology');
		page.submit();
		return page;
	}

	it('tells the student when the NIM is already registered, instead of a vague failure', () => {
		const taken = { status: 409, error: { detail: 'That NIM is already registered.' } };
		const page = submitWith(() => throwError(() => taken));
		expect(page.errorMessage()).toBe('That NIM is already registered.');
		expect(page.submitting()).toBe(false);
	});

	it('keeps the generic message for any other failure and never shows a non-409 server text', () => {
		const down = { status: 500, error: { detail: 'secret internals' } };
		const page = submitWith(() => throwError(() => down));
		expect(page.errorMessage()).toBe('Unable to save your details. Please try again.');
	});

	it('refuses an invalid NIM or a missing major without calling the server', () => {
		const { page, saveOnboarding } = setup();
		page.nim.set(-5);
		page.major.set('');
		page.submit();
		expect(saveOnboarding).not.toHaveBeenCalled();
		expect(page.errorMessage()).toContain('valid NIM');
	});
});
