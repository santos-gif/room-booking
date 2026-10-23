import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, of, Subject, throwError } from 'rxjs';
import { Availability, AvailableSlot } from '../types/booking-form';
import { loadAvailability } from './availability-loader';
import { BookingFormService } from './booking-form.service';

const slot = (hour: string): AvailableSlot => ({
	start_time: `2030-01-08T${hour}:00:00+07:00`,
	end_time: `2030-01-08T${Number(hour) + 1}:00:00+07:00`,
	available: true,
});
const answer = (...hours: string[]): Availability => ({
	bookings_used: 0,
	bookings_remaining: 3,
	slots: hours.map(slot),
});

describe('loadAvailability (a stale slot list never shows)', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	// Runs the effect, then lets the zero-delay timer inside visibleTimer fire (it is not synchronous).
	const flush = () => {
		TestBed.tick();
		vi.advanceTimersByTime(0);
	};

	function setup(
		api: (date: string, room: 1 | 2) => Observable<Availability>,
		excludeId?: string,
	) {
		const date = signal('2030-01-08');
		const room = signal<1 | 2>(1);
		const reload = signal(0);
		const calls: Array<[string, number]> = [];
		const service = {
			availability: (d: string, r: 1 | 2) => {
				calls.push([d, r]);
				return api(d, r);
			},
		} as unknown as BookingFormService;
		const loader = TestBed.runInInjectionContext(() =>
			loadAvailability(service, { date, room, reload, excludeId }),
		);
		flush();
		return { date, room, reload, calls, loader };
	}

	it('loads once, then shows the slots', () => {
		const { loader, calls } = setup(() => of(answer('09', '10')));
		expect(calls).toEqual([['2030-01-08', 1]]);
		expect(loader.loading()).toBe(false);
		expect(loader.slots().length).toBe(2);
	});

	it('empties the slots the moment the room changes, and shows loading until the new answer', () => {
		const second = new Subject<Availability>();
		let first = true;
		const { loader, room } = setup(() => {
			if (first) {
				first = false;
				return of(answer('16'));
			}
			return second;
		});
		expect(loader.slots().length).toBe(1);

		room.set(2);
		flush();
		expect(loader.slots()).toEqual([]);
		expect(loader.loading()).toBe(true);

		second.next(answer('09'));
		expect(loader.loading()).toBe(false);
		expect(loader.slots()[0].start_time).toContain('T09:');
	});

	it('refetches when reload is bumped (after a booking attempt)', () => {
		const { calls, reload } = setup(() => of(answer('09')));
		reload.update((n) => n + 1);
		flush();
		expect(calls.length).toBe(2);
	});

	it('says "no free slot" only when slots loaded and every one is taken', () => {
		const taken = { ...slot('09'), available: false };
		const free = setup(() => of(answer('09')));
		expect(free.loader.noFreeSlot()).toBe(false);
		TestBed.resetTestingModule();
		const none = setup(() => of({ ...answer(), slots: [] }));
		expect(none.loader.noFreeSlot()).toBe(false); // nothing at all is not "all taken"
		TestBed.resetTestingModule();
		const full = setup(() => of({ ...answer(), slots: [taken] }));
		expect(full.loader.noFreeSlot()).toBe(true);
	});

	it('flags the booking as gone on a 404 only when one is being updated', () => {
		const notFound = () => throwError(() => ({ status: 404 }));
		expect(setup(notFound).loader.gone()).toBe(false); // nothing is being updated
		TestBed.resetTestingModule();
		expect(setup(notFound, 'b1').loader.gone()).toBe(true);
	});

	it('shows an error, not stale slots, when the first load fails', () => {
		const { loader } = setup(() => throwError(() => new Error('down')));
		expect(loader.slots()).toEqual([]);
		expect(loader.loading()).toBe(false);
		expect(loader.error()).toContain('Unable to refresh availability');
	});
});
