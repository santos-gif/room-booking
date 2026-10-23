import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { BookingAppointment } from '../types/booking-form';
import { BookingFormService } from '../service/booking-form.service';
import { loadUpdateTarget } from './update-target';

const booking = (id: string, room: 1 | 2 = 2): BookingAppointment => ({
	id,
	booker_id: 'u1',
	room_number: room,
	start_time: '2030-01-08T03:00:00Z', // 10:00 on 2030-01-08 in Jakarta
	end_time: '2030-01-08T04:00:00Z',
	status: 'confirmed',
	sync_status: 'synced',
});
const api = (mine: ReturnType<BookingFormService['mine']>) =>
	({ mine: () => mine }) as unknown as BookingFormService;

describe('loadUpdateTarget (update mode never saves a booking that is gone)', () => {
	function setup(mine: ReturnType<BookingFormService['mine']>, id: string | null) {
		const room = signal<1 | 2>(1);
		const date = signal('2030-02-01');
		const onOpen = vi.fn();
		const target = TestBed.runInInjectionContext(() =>
			loadUpdateTarget(api(mine), id, { room, date, onOpen }),
		);
		TestBed.tick();
		return { target, room, date, onOpen };
	}

	it('opens the view on the booking’s own room and day, and clears the old selection', () => {
		const { room, date, onOpen, target } = setup(
			of([booking('a', 1), booking('b', 2)]),
			'b',
		);
		expect(room()).toBe(2);
		expect(date()).toBe('2030-01-08');
		expect(onOpen).toHaveBeenCalledTimes(1);
		expect(target.missing()).toBe(false);
	});

	it('labels the current time only while its own room is showing', () => {
		const { room, target } = setup(of([booking('b', 2)]), 'b');
		expect(target.currentStart()).toBe('2030-01-08T03:00:00Z');
		room.set(1);
		expect(target.currentStart()).toBeNull();
	});

	it('reports missing when the booking is not in the list (cancelled or deleted in Calendar)', () => {
		const { target, onOpen, room } = setup(of([booking('a')]), 'zzz');
		expect(target.missing()).toBe(true);
		expect(target.currentStart()).toBeNull();
		expect(onOpen).not.toHaveBeenCalled();
		expect(room()).toBe(1); // the view is left alone
	});

	it('reports missing when the lookup itself fails', () => {
		const { target } = setup(
			throwError(() => new Error('down')),
			'a',
		);
		expect(target.missing()).toBe(true);
	});

	it('does nothing when not in update mode', () => {
		const { target, onOpen } = setup(
			throwError(() => new Error('never called')),
			null,
		);
		expect(target.missing()).toBe(false);
		expect(target.currentStart()).toBeNull();
		expect(onOpen).not.toHaveBeenCalled();
	});
});
