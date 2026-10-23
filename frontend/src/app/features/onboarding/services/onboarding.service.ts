import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AuthenticatedUser, Major } from '../../../core/types/auth';

@Injectable()
export class OnboardingService {
	private readonly auth = inject(AuthService);

	/** Goes through AuthService so the cached user the route guards read is updated too. */
	saveOnboarding(nim: number, major: Major): Observable<AuthenticatedUser> {
		return this.auth.saveOnboarding(nim, major);
	}
}
