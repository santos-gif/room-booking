import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { BookingsStore } from '../../../core/services/bookings-store';
import { MyBookingsService } from './my-bookings.service';

describe('MyBookingsService (a read-only filter over the shared store)', () => {
	function setup() {
		const store = {
			appointments: signal([]),
			loaded: signal(true),
			error: signal(''),
			refresh: vi.fn(),
			cancel: vi.fn(() => of(undefined)),
			invalidate: vi.fn(),
		};
		TestBed.configureTestingModule({
			providers: [MyBookingsService, { provide: BookingsStore, useValue: store }],
		});
		return { service: TestBed.inject(MyBookingsService), store };
	}

	it('shows what the store holds, and the page cannot write to it', () => {
		const { service, store } = setup();
		store.error.set('Unable to load your bookings. Please try again.');
		expect(service.error()).toContain('Unable to load');
		expect('set' in service.appointments).toBe(false);
	});

	it('forwards refresh and cancel, and offers nothing else of the store', () => {
		const { service, store } = setup();
		service.refresh(30_000);
		service.refresh();
		service.cancel('b1').subscribe();
		expect(store.refresh).toHaveBeenNthCalledWith(1, 30_000);
		expect(store.refresh).toHaveBeenNthCalledWith(2, undefined);
		expect(store.cancel).toHaveBeenCalledWith('b1');
		expect('invalidate' in service).toBe(false);
	});
});
