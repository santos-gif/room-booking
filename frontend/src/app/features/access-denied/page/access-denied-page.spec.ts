import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { AccessDeniedPage } from './access-denied-page';

describe('AccessDeniedPage (a refused sign-in gets a clear answer)', () => {
	function render(reason?: string) {
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{
					provide: ActivatedRoute,
					useValue: {
						snapshot: {
							queryParamMap: convertToParamMap(
								reason ? { reason } : {},
							),
						},
					},
				},
			],
		});
		const fixture = TestBed.createComponent(AccessDeniedPage);
		fixture.detectChanges();
		return fixture.nativeElement as HTMLElement;
	}

	it('explains a non-Pradita email and points to the right accounts', () => {
		const text = render('university_email_required').textContent;
		expect(text).toContain('Access denied');
		expect(text).toContain('@student.pradita.ac.id');
	});

	it('explains an unverified email and an account that needs linking', () => {
		expect(render('verified_email_required').textContent).toContain('verified');
		TestBed.resetTestingModule();
		expect(render('account_link_required').textContent).toContain('administrator');
	});

	it('shows a generic message for an unknown or missing reason, never a blank page', () => {
		expect(render('whatever').textContent).toContain('does not have access');
		TestBed.resetTestingModule();
		// Names every object has must not count as reasons.
		expect(render('constructor').textContent).toContain('does not have access');
		TestBed.resetTestingModule();
		expect(render().textContent).toContain('does not have access');
	});

	it('always offers a way back to sign in', () => {
		const link = render('university_email_required').querySelector('a');
		expect(link?.textContent?.trim()).toBe('Back to sign in');
		expect(link?.getAttribute('href')).toBe('/');
	});
});
