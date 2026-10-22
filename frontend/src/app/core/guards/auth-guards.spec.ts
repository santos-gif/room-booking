import { TestBed } from '@angular/core/testing';
import {
	ActivatedRouteSnapshot,
	provideRouter,
	Router,
	RouterStateSnapshot,
	UrlTree,
} from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../services/auth-service';
import { authenticatedGuard } from './auth-guards';

describe('authenticatedGuard (a server problem is not the same as being signed out)', () => {
	function run(me: Observable<unknown>, url: string) {
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{ provide: AuthService, useValue: { me: () => me } },
			],
		});
		const state = { url } as RouterStateSnapshot;
		const result = TestBed.runInInjectionContext(() =>
			authenticatedGuard({} as ActivatedRouteSnapshot, state),
		) as Observable<boolean | UrlTree>;
		let outcome: boolean | UrlTree | undefined;
		result.subscribe((value) => (outcome = value));
		return { outcome: () => outcome, router: TestBed.inject(Router) };
	}
	const done = { onboarding_complete: true };

	it('lets a signed-in, onboarded student through', () => {
		expect(run(of(done), '/my-bookings').outcome()).toBe(true);
	});

	it('sends a student without a profile to onboarding, even when the URL has a query string', () => {
		const { outcome, router } = run(
			of({ onboarding_complete: false }),
			'/my-bookings?x=1',
		);
		expect(router.serializeUrl(outcome() as UrlTree)).toBe('/onboarding');
		TestBed.resetTestingModule();
		const again = run(of({ onboarding_complete: false }), '/onboarding?x=1');
		expect(again.outcome()).toBe(true);
	});

	it('sends a signed-out student (401) to the login page', () => {
		const { outcome, router } = run(
			throwError(() => ({ status: 401 })),
			'/my-bookings',
		);
		expect(router.serializeUrl(outcome() as UrlTree)).toBe('/');
	});

	it('tells the student the server is unreachable (5xx / offline) instead of treating them as signed out', () => {
		for (const status of [0, 500, 503]) {
			const { outcome, router } = run(
				throwError(() => ({ status })),
				'/my-bookings',
			);
			expect(router.serializeUrl(outcome() as UrlTree)).toBe(
				'/?auth_error=server_unavailable',
			);
			TestBed.resetTestingModule();
		}
	});
});
