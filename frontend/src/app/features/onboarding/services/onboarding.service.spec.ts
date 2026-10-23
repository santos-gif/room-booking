import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { OnboardingService } from './onboarding.service';

describe('OnboardingService', () => {
	it('saves through AuthService so the cached user (read by the route guards) is updated', () => {
		const user = { onboarding_complete: true };
		const saveOnboarding = vi.fn(() => of(user));
		TestBed.configureTestingModule({
			providers: [OnboardingService, { provide: AuthService, useValue: { saveOnboarding } }],
		});
		let saved: unknown;
		TestBed.inject(OnboardingService)
			.saveOnboarding(2510101051, 'Information Technology' as never)
			.subscribe((value) => (saved = value));
		expect(saveOnboarding).toHaveBeenCalledWith(2510101051, 'Information Technology');
		expect(saved).toBe(user);
	});
});
