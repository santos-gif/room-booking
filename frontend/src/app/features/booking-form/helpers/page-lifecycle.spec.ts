import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { NavigationLock } from '../../../core/services/navigation-lock';
import { BookingFormService } from '../service/booking-form.service';
import { guardBookingPage } from './page-lifecycle';

describe('guardBookingPage', () => {
	function setup() {
		const invalidate = vi.fn();
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{
					provide: BookingFormService,
					useValue: { invalidateBookings: invalidate },
				},
			],
		});
		const saving = signal(false);
		const gone = signal(false);
		const navigate = vi
			.spyOn(TestBed.inject(Router), 'navigate')
			.mockResolvedValue(true);
		const hold = signal(false);
		TestBed.runInInjectionContext(() => guardBookingPage(saving, gone, hold));
		TestBed.tick();
		return {
			saving,
			gone,
			hold,
			navigate,
			invalidate,
			lock: TestBed.inject(NavigationLock),
		};
	}

	it('locks the navbar only while saving, and unlocks when the page is destroyed', () => {
		const { saving, lock } = setup();
		expect(lock.locked()).toBe(false);
		saving.set(true);
		TestBed.tick();
		expect(lock.locked()).toBe(true);
		TestBed.resetTestingModule();
		expect(lock.locked()).toBe(false);
	});

	it('goes back to My bookings with a fresh list when the booking is gone', () => {
		const { gone, navigate, invalidate } = setup();
		expect(navigate).not.toHaveBeenCalled();
		gone.set(true);
		TestBed.tick();
		expect(invalidate).toHaveBeenCalledOnce();
		expect(navigate).toHaveBeenCalledWith(['/my-bookings']);
	});

	it('waits for the save and the result dialog before leaving', () => {
		const { saving, gone, hold, navigate } = setup();
		saving.set(true);
		hold.set(true);
		gone.set(true);
		TestBed.tick();
		expect(navigate).not.toHaveBeenCalled();
		saving.set(false);
		TestBed.tick();
		expect(navigate).not.toHaveBeenCalled(); // dialog still open
		hold.set(false);
		TestBed.tick();
		expect(navigate).toHaveBeenCalledWith(['/my-bookings']);
	});
});
