import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Appointment } from '../types/appointment';
import { BookingsStore } from './bookings-store';

const booking = (id: string): Appointment => ({
	id,
	booker_id: 'u1',
	room_number: 1,
	start_time: '2030-01-08T02:00:00Z',
	end_time: '2030-01-08T03:00:00Z',
	status: 'confirmed',
	sync_status: 'synced',
});
const isList = (r: { url: string }) => r.url.endsWith('/appointments/');

describe('BookingsStore (the list is cached, but never wrong after a change)', () => {
	let store: BookingsStore;
	let http: HttpTestingController;

	beforeEach(() => {
		vi.useFakeTimers();
		TestBed.configureTestingModule({
			providers: [provideHttpClient(), provideHttpClientTesting()],
		});
		store = TestBed.inject(BookingsStore);
		http = TestBed.inject(HttpTestingController);
	});

	afterEach(() => {
		http.verify();
		vi.useRealTimers();
	});

	it('asks the server with verify=true, so deletions in Google Calendar are noticed', () => {
		store.refresh();
		const request = http.expectOne(isList);
		expect(request.request.params.get('verify')).toBe('true');
		request.flush([booking('a')]);
		expect(store.loaded()).toBe(true);
		expect(store.appointments().map((a) => a.id)).toEqual(['a']);
	});

	it('does not ask again within a minute, and asks again after it', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		store.refresh(); // cached: no request (http.verify would fail otherwise)
		vi.advanceTimersByTime(61_000);
		store.refresh();
		http.expectOne(isList).flush([booking('a'), booking('b')]);
		expect(store.appointments().length).toBe(2);
	});

	it('lets the My bookings poll ask again sooner than the default minute', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		vi.advanceTimersByTime(36_000);
		store.refresh(); // default: still fresh, no request
		store.refresh(35_000); // the poll: older than 35 s, so it asks
		http.expectOne(isList).flush([]);
		expect(store.appointments()).toEqual([]);
	});

	it('forgets the cache after a booking changed, and hides the stale list until the new one arrives', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		store.invalidate();
		expect(store.loaded()).toBe(false);
		store.refresh();
		http.expectOne(isList).flush([booking('a'), booking('new')]);
		expect(store.loaded()).toBe(true);
		expect(store.appointments().length).toBe(2);
	});

	it('ignores an answer that was already in flight when a booking changed, and asks again', () => {
		store.refresh();
		const stale = http.expectOne(isList);
		store.invalidate();
		stale.flush([booking('old')]);
		expect(store.appointments()).toEqual([]);
		expect(store.loaded()).toBe(false);
		http.expectOne(isList).flush([booking('fresh')]);
		expect(store.appointments().map((a) => a.id)).toEqual(['fresh']);
		expect(store.loaded()).toBe(true);
	});

	it('keeps the cached list when a reload fails, and retries on the next visit', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		vi.advanceTimersByTime(61_000);
		store.refresh();
		http.expectOne(isList).flush('down', { status: 500, statusText: 'Server Error' });
		expect(store.appointments().map((a) => a.id)).toEqual(['a']);
		expect(store.error()).toContain('Unable to load');
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		expect(store.error()).toBe('');
	});

	it('does not bring a cancelled booking back when an older list request lands after the cancel', () => {
		store.refresh();
		const older = http.expectOne(isList); // started before the cancel
		store.cancel('a').subscribe();
		http.expectOne((r) => r.method === 'DELETE').flush(null);
		older.flush([booking('a'), booking('b')]); // still contains the cancelled booking
		expect(store.appointments().map((x) => x.id)).not.toContain('a');
		http.expectOne(isList).flush([booking('b')]); // the store asked again
		expect(store.appointments().map((x) => x.id)).toEqual(['b']);
	});

	it('shows the error alone, not an outdated list, when the reload after a booking fails', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a')]);
		store.invalidate(); // a booking was just made; the cached list is wrong now
		store.refresh();
		http.expectOne(isList).flush('down', { status: 500, statusText: 'Server Error' });
		expect(store.appointments()).toEqual([]);
		expect(store.error()).toContain('Unable to load');
		expect(store.loaded()).toBe(true);
	});

	it('drops a cancelled booking from the list at once', () => {
		store.refresh();
		http.expectOne(isList).flush([booking('a'), booking('b')]);
		store.cancel('a').subscribe();
		http.expectOne(
			(r) => r.method === 'DELETE' && r.url.endsWith('/appointments/a'),
		).flush(null);
		expect(store.appointments().map((a) => a.id)).toEqual(['b']);
	});
});
