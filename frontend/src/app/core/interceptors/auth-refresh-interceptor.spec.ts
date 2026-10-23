import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { authRefreshInterceptor } from './auth-refresh-interceptor';

const unauthorized = { status: 401, statusText: 'Unauthorized' };

describe('authRefreshInterceptor', () => {
	let client: HttpClient;
	let http: HttpTestingController;
	const router = { url: '/my-bookings', navigateByUrl: vi.fn() };

	beforeEach(() => {
		TestBed.configureTestingModule({
			providers: [
				provideHttpClient(withInterceptors([authRefreshInterceptor])),
				provideHttpClientTesting(),
				{ provide: Router, useValue: router },
			],
		});
		client = TestBed.inject(HttpClient);
		http = TestBed.inject(HttpTestingController);
	});

	afterEach(() => {
		document.cookie = 'csrf_token=; max-age=0';
		http.verify();
	});

	it('refreshes the session and retries once when a signed-in request gets 401', () => {
		document.cookie = 'csrf_token=abc';
		let body: unknown;
		client.get('/api/bookings').subscribe((value) => (body = value));

		http.expectOne('/api/bookings').flush('expired', unauthorized);
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush({});
		const retry = http.expectOne('/api/bookings');
		expect(retry.request.headers.get('X-Retry-Attempt')).toBe('1');
		retry.flush({ ok: true });

		expect(body).toEqual({ ok: true });
	});

	it('keeps the retry own error: a 409 after a successful refresh is not an expired session', () => {
		document.cookie = 'csrf_token=abc';
		router.navigateByUrl.mockClear();
		let status: number | undefined;
		client.get('/api/bookings').subscribe({ error: (e) => (status = e.status) });

		http.expectOne('/api/bookings').flush('expired', unauthorized);
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush({});
		http.expectOne('/api/bookings').flush('taken', {
			status: 409,
			statusText: 'Conflict',
		});

		expect(status).toBe(409);
		expect(router.navigateByUrl).not.toHaveBeenCalled();
	});

	it('does not try to refresh when nobody is signed in (no csrf_token cookie)', () => {
		let status: number | undefined;
		client.get('/api/auth/me').subscribe({ error: (e) => (status = e.status) });

		http.expectOne('/api/auth/me').flush('no session', unauthorized);

		expect(status).toBe(401);
		http.expectNone((r) => r.url.endsWith('/auth/refresh'));
	});

	it('sends the student back to sign-in when the session cannot be renewed', () => {
		document.cookie = 'csrf_token=abc';
		router.navigateByUrl.mockClear();
		client.get('/api/bookings').subscribe({ error: () => undefined });

		http.expectOne('/api/bookings').flush('expired', unauthorized);
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush('gone', unauthorized);

		expect(router.navigateByUrl).toHaveBeenCalledWith('/?auth_error=session_expired');
	});

	it('gives up after one retry instead of looping', () => {
		document.cookie = 'csrf_token=abc';
		let status: number | undefined;
		client.get('/api/bookings').subscribe({ error: (e) => (status = e.status) });

		http.expectOne('/api/bookings').flush('expired', unauthorized);
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush({});
		http.expectOne('/api/bookings').flush('still expired', unauthorized);

		expect(status).toBe(401);
	});
});
