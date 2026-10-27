import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { AuthService } from '../services/auth-service';
import { authRefreshInterceptor } from './auth-refresh-interceptor';

const unauthorized = { status: 401, statusText: 'Unauthorized' };

describe('authRefreshInterceptor', () => {
	let client: HttpClient;
	let http: HttpTestingController;
	let closed: Subject<void>;
	const router = { url: '/my-bookings', navigateByUrl: vi.fn() };
	const dialog = { getDialogById: vi.fn(), open: vi.fn() };

	beforeEach(() => {
		closed = new Subject<void>();
		router.url = '/my-bookings';
		router.navigateByUrl.mockClear();
		dialog.getDialogById.mockReset();
		dialog.open.mockReset().mockImplementation(() => ({ afterClosed: () => closed }));
		TestBed.configureTestingModule({
			providers: [
				provideHttpClient(withInterceptors([authRefreshInterceptor])),
				provideHttpClientTesting(),
				{ provide: Router, useValue: router },
				{ provide: MatDialog, useValue: dialog },
			],
		});
		client = TestBed.inject(HttpClient);
		http = TestBed.inject(HttpTestingController);
	});

	afterEach(() => {
		document.cookie = 'csrf_token=; max-age=0';
		http.verify();
	});

	/** A request that comes back 401 with no way to renew (nobody signed in). */
	const rejected = (url: string) => {
		client.get(url).subscribe({ error: () => undefined });
		http.expectOne(url).flush('no session', unauthorized);
	};

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

	it('tells the student the session ended, and sends them to sign-in only once they confirm', () => {
		document.cookie = 'csrf_token=abc';
		client.get('/api/bookings').subscribe({ error: () => undefined });

		http.expectOne('/api/bookings').flush('expired', unauthorized);
		http.expectOne((r) => r.url.endsWith('/auth/refresh')).flush('gone', unauthorized);

		expect(dialog.open).toHaveBeenCalledTimes(1);
		expect(router.navigateByUrl).not.toHaveBeenCalled();
		closed.next();
		expect(router.navigateByUrl).toHaveBeenCalledWith('/');
	});

	it('shows the same notice, without a refresh, when the cookies are already gone (signed out in another tab)', () => {
		let status: number | undefined;
		client.get('/api/appointments').subscribe({ error: (e) => (status = e.status) });

		http.expectOne('/api/appointments').flush('no session', unauthorized);

		expect(status).toBe(401);
		expect(dialog.open).toHaveBeenCalledTimes(1);
		http.expectNone((r) => r.url.endsWith('/auth/refresh'));
		closed.next();
		expect(router.navigateByUrl).toHaveBeenCalledWith('/');
	});

	it('opens only one notice while one is already showing', () => {
		dialog.getDialogById.mockReturnValue({});
		rejected('/api/appointments');
		expect(dialog.open).not.toHaveBeenCalled();
	});

	it('stays quiet on the sign-in page and for the who-am-I check of a first visit', () => {
		rejected('/api/auth/me');
		router.url = '/?auth_error=session_expired';
		rejected('/api/appointments');
		expect(dialog.open).not.toHaveBeenCalled();
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
