import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { BookingFormService } from '../service/booking-form.service';
import { BookingAppointment } from '../types/booking-form';
import { BookingFormPage } from './booking-form-page';

const booking: BookingAppointment = {
	id: 'b1',
	booker_id: 'u1',
	room_number: 2,
	start_time: '2030-01-08T03:00:00Z', // 10:00 in Jakarta
	end_time: '2030-01-08T04:00:00Z',
	status: 'confirmed',
	sync_status: 'synced',
};
const freeSlot = {
	start_time: '2030-01-08T11:00:00+07:00',
	end_time: '2030-01-08T12:00:00+07:00',
	available: true,
};

describe('BookingFormPage in update mode (never saves a booking that is gone)', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	function setup(mine: Observable<BookingAppointment[]>) {
		const api = {
			availability: vi.fn(() =>
				of({ bookings_used: 1, bookings_remaining: 2, slots: [freeSlot] }),
			),
			mine: () => mine,
			book: vi.fn(() => of({})),
			reschedule: vi.fn(() => of({})),
			invalidateBookings: vi.fn(),
		};
		TestBed.configureTestingModule({
			providers: [
				provideRouter([{ path: 'my-bookings', children: [] }]),
				{
					provide: AuthService,
					useValue: { login: vi.fn(), logout: vi.fn(), me: () => of({ role: 'student' }) },
				},
				{ provide: MatDialog, useValue: { open: vi.fn() } },
				{
					provide: ActivatedRoute,
					useValue: {
						snapshot: {
							queryParamMap: convertToParamMap({
								reschedule: 'b1',
							}),
						},
					},
				},
			],
		});
		TestBed.overrideComponent(BookingFormPage, {
			set: { providers: [{ provide: BookingFormService, useValue: api }] },
		});
		const fixture = TestBed.createComponent(BookingFormPage);
		// Effects run on detectChanges; the availability timer fires on the next tick.
		for (let i = 0; i < 3; i++) {
			fixture.detectChanges();
			vi.advanceTimersByTime(0);
		}
		fixture.detectChanges();
		return { fixture, page: fixture.componentInstance, api };
	}

	it('blocks saving, says so and returns to My bookings when the booking is not in the list any more', () => {
		const navigate = vi.spyOn(Router.prototype, 'navigate').mockResolvedValue(true);
		const { fixture, page, api } = setup(of([]));
		TestBed.tick();
		expect(navigate).toHaveBeenCalledWith(['/my-bookings']);
		expect((fixture.nativeElement as HTMLElement).textContent).toContain(
			'could not find that booking',
		);
		page.pick(freeSlot);
		page.confirmBooking();
		expect(api.reschedule).not.toHaveBeenCalled();
		const slots = [
			...(
				fixture.nativeElement as HTMLElement
			).querySelectorAll<HTMLButtonElement>('.slot'),
		];
		expect(slots.length).toBeGreaterThan(0);
		expect(slots.every((slot) => slot.disabled)).toBe(true);
	});

	it('opens on the booking’s own room and day, and saves through the update endpoint', () => {
		const { page, api } = setup(of([booking]));
		expect(page.roomNumber()).toBe(2);
		expect(page.bookingDate()).toBe('2030-01-08');
		page.pick(freeSlot);
		page.confirmBooking();
		expect(api.reschedule).toHaveBeenCalledWith('b1', {
			room_number: 2,
			start_time: freeSlot.start_time,
		});
		expect(api.book).not.toHaveBeenCalled();
		expect(page.resultMessage()).toBe('Booking updated successfully.');
	});
});
