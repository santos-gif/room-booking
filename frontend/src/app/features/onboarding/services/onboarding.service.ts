import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser, Major } from '../../../core/types/auth';

/**
 * What the onboarding page needs from the server. Saving goes through AuthService, never its own HTTP
 * call: AuthService caches the signed-in user, and the route guards read that cache, so a save that
 * skipped it would send the student straight back to onboarding.
 */
@Injectable()
export class OnboardingService {
	private readonly auth = inject(AuthService);

	/** The signed-in student's current profile (the Profile page edits it). */
	loadProfile(): Observable<AuthenticatedUser> {
		return this.auth.me();
	}

	saveOnboarding(nim: number, major: Major): Observable<AuthenticatedUser> {
		return this.auth.saveOnboarding(nim, major);
	}
}
