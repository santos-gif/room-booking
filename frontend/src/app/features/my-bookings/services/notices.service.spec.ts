import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NoticesService } from './notices.service';

const NOTICE = {
	id: 'n1',
	message: 'Your booking was cancelled by staff: AC repair',
	created_at: '2030-01-01T00:00:00Z',
};

describe('NoticesService (the notices routes, no state of its own)', () => {
	function setup() {
		TestBed.configureTestingModule({
			providers: [
				NoticesService,
				provideHttpClient(),
				provideHttpClientTesting(),
			],
		});
		return {
			service: TestBed.inject(NoticesService),
			http: TestBed.inject(HttpTestingController),
		};
	}

	it('lists the notices the server has for the student', () => {
		const { service, http } = setup();
		let got: unknown;
		service.list().subscribe((list) => (got = list));
		http.expectOne((r) => r.url.endsWith('/appointments/notices')).flush([NOTICE]);
		expect(got).toEqual([NOTICE]);
	});

	it('marks one notice as seen with a POST', () => {
		const { service, http } = setup();
		service.dismiss('n1').subscribe();
		expect(
			http.expectOne((r) => r.url.endsWith('/notices/n1/seen')).request.method,
		).toBe('POST');
	});
});
