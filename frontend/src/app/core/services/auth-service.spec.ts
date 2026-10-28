import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthenticatedUser } from '../types/auth';
import { AuthService } from './auth-service';

const user: AuthenticatedUser = {
	id: 'u1',
	email: 'student@student.pradita.ac.id',
	name: 'Test Student',
	nim: 2510101051,
	major: 'Management',
	onboarding_complete: true,
	role: 'student',
};
const unauthorized = { status: 401, statusText: 'Unauthorized' };
const isMe = (r: { url: string }) => r.url.endsWith('/auth/me');

describe('AuthService (one /auth/me round trip per session, not per page)', () => {
	let service: AuthService;
	let http: HttpTestingController;

	beforeEach(() => {
		TestBed.configureTestingModule({
			providers: [provideHttpClient(), provideHttpClientTesting()],
		});
		service = TestBed.inject(AuthService);
		http = TestBed.inject(HttpTestingController);
	});

	afterEach(() => http.verify());

	it('asks the server once and reuses the answer for later navigations', () => {
		const seen: AuthenticatedUser[] = [];
		service.me().subscribe((value) => seen.push(value));
		http.expectOne(isMe).flush(user);
		service.me().subscribe((value) => seen.push(value));
		expect(seen).toEqual([user, user]);
	});

	it('does not remember a failed lookup', () => {
		service.me().subscribe({ error: () => undefined });
		http.expectOne(isMe).flush('no session', unauthorized);
		service.me().subscribe();
		http.expectOne(isMe).flush(user);
	});

	it('forgets the user when the session cannot be refreshed', () => {
		service.me().subscribe();
		http.expectOne(isMe).flush(user);
		service.refresh().subscribe({ error: () => undefined });
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush(
			'expired',
			unauthorized,
		);
		service.me().subscribe();
		http.expectOne(isMe).flush(user);
	});

	it('shares ONE refresh call between requests that fail at the same time', () => {
		service.refresh().subscribe();
		service.refresh().subscribe();
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush({});
		// A later refresh is a new call again.
		service.refresh().subscribe();
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush({});
	});

	it('serves the saved profile after onboarding without asking again', () => {
		const saved = { ...user, onboarding_complete: true };
		service.saveOnboarding(2510101051, 'Management').subscribe();
		http.expectOne((r) => r.url.endsWith('/auth/onboarding')).flush(saved);
		let seen: AuthenticatedUser | undefined;
		service.me().subscribe((value) => (seen = value));
		expect(seen).toEqual(saved);
	});
});
