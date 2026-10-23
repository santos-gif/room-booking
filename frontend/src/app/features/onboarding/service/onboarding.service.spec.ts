import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { OnboardingService } from './onboarding.service';

describe('OnboardingService (always through AuthService, so the route guards see the change)', () => {
	function setup() {
		const auth = {
			saveOnboarding: vi.fn(() => of({ onboarding_complete: true })),
			me: vi.fn(() => of({})),
		};
		TestBed.configureTestingModule({
			providers: [OnboardingService, { provide: AuthService, useValue: auth }],
		});
		return { service: TestBed.inject(OnboardingService), auth };
	}

	it('saves through AuthService.saveOnboarding, which refreshes the cached user', () => {
		const { service, auth } = setup();
		service.saveOnboarding(2510101051, 'Information Technology').subscribe();
		expect(auth.saveOnboarding).toHaveBeenCalledWith(
			2510101051,
			'Information Technology',
		);
	});

	it('loads the profile through the cached AuthService.me()', () => {
		const { service, auth } = setup();
		service.loadProfile().subscribe();
		expect(auth.me).toHaveBeenCalledOnce();
	});
});
