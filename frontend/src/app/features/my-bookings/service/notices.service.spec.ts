import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NoticesService } from './notices.service';

const NOTICE = {
	id: 'n1',
	message: 'Your booking was cancelled by staff: AC repair',
	created_at: '2030-01-01T00:00:00Z',
};

describe('NoticesService (messages about bookings staff cancelled)', () => {
	function setup() {
		TestBed.configureTestingModule({
			providers: [provideHttpClient(), provideHttpClientTesting()],
		});
		return {
			service: TestBed.inject(NoticesService),
			http: TestBed.inject(HttpTestingController),
		};
	}

	it('loads the notices and hides one at once when it is dismissed', () => {
		const { service, http } = setup();
		service.load();
		http.expectOne((r) => r.url.endsWith('/appointments/notices')).flush([NOTICE]);
		expect(service.notices()).toEqual([NOTICE]);

		service.dismiss('n1');

		expect(service.notices()).toEqual([]);
		expect(
			http.expectOne((r) => r.url.endsWith('/notices/n1/seen')).request.method,
		).toBe('POST');
	});

	it('never breaks the page when notices cannot be loaded', () => {
		const { service, http } = setup();
		service.load();
		http.expectOne((r) => r.url.endsWith('/appointments/notices')).error(
			new ProgressEvent('error'),
		);
		expect(service.notices()).toEqual([]);
	});

	it('asks the server again if dismissing fails, so a notice is never lost silently', () => {
		const { service, http } = setup();
		service.dismiss('n1');
		http.expectOne((r) => r.url.endsWith('/notices/n1/seen')).error(
			new ProgressEvent('error'),
		);
		http.expectOne((r) => r.url.endsWith('/appointments/notices')).flush([NOTICE]);
		expect(service.notices()).toEqual([NOTICE]);
	});
});
