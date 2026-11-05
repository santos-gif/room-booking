import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { LoginService } from './login.service';

describe('LoginService (the login page never crashes and refusals are routed)', () => {
	function setup(authError: string | null, me = of({})) {
		const params = convertToParamMap(authError ? { auth_error: authError } : {});
		TestBed.configureTestingModule({
			providers: [
				LoginService,
				{
					provide: AuthService,
					useValue: { me: () => me, login: vi.fn() },
				},
				{
					provide: ActivatedRoute,
					useValue: {
						snapshot: { queryParamMap: params },
						queryParamMap: of(params),
					},
				},
			],
		});
		return TestBed.inject(LoginService);
	}

	it('sends refused sign-ins to the Access denied page, with the reason', () => {
		for (const code of [
			'university_email_required',
			'verified_email_required',
			'account_link_required',
		]) {
			expect(setup(code).deniedReason()).toBe(code);
			TestBed.resetTestingModule();
		}
	});

	it('keeps ordinary problems on the form: cancelled, failed, expired session, server down', () => {
		for (const code of [
			'google_access_denied',
			'google_exchange_failed',
			'session_expired',
			'server_unavailable',
		]) {
			const service = setup(code);
			expect(service.deniedReason()).toBe('');
			expect(service.errorMessage()).not.toBe('');
			TestBed.resetTestingModule();
		}
	});

	it('has no message at all for a normal visit or an unknown code', () => {
		expect(setup(null).errorMessage()).toBe('');
		TestBed.resetTestingModule();
		expect(setup('made_up').errorMessage()).toBe('');
		TestBed.resetTestingModule();
		// Names every object has must not count as codes.
		expect(setup('constructor').errorMessage()).toBe('');
	});

	it('treats ANY failure of the who-am-I call (401, 500, offline) as "nobody signed in"', () => {
		for (const status of [401, 404, 500, 0]) {
			const service = setup(null, throwError(() => ({ status })) as never);
			let user: unknown = 'unset';
			service.me().subscribe((value) => (user = value));
			expect(user).toBeNull();
			TestBed.resetTestingModule();
		}
	});
});
