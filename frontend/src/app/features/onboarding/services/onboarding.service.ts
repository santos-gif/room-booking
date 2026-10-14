import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthenticatedUser, Major } from '../../../core/types/auth';

@Injectable()
export class OnboardingService {
	private readonly http = inject(HttpClient);

	saveOnboarding(nim: number, major: Major): Observable<AuthenticatedUser> {
		return this.http.post<AuthenticatedUser>(
			`${environment.apiUrl}/auth/onboarding`,
			{ nim, major },
		);
	}
}
