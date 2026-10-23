import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { OnboardingPage } from './onboarding-page';

describe('OnboardingPage', () => {
	function setup() {
		const saveOnboarding = vi.fn(() => of({ onboarding_complete: true }));
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

	it('refuses an invalid NIM or a missing major without calling the server', () => {
		const { page, saveOnboarding } = setup();
		page.nim.set(-5);
		page.major.set('');
		page.submit();
		expect(saveOnboarding).not.toHaveBeenCalled();
		expect(page.errorMessage()).toContain('valid NIM');
	});
});
