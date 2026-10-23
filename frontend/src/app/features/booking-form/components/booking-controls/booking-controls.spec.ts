import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BookingControls, isWeekday } from './booking-controls';

/** The component's protected members the tests reach into. */
interface Picking {
	pick(event: { value: Date | null }): void;
	minDate: Date;
	maxDate: Date;
}

function render(room: 1 | 2 = 1) {
	const fixture = TestBed.createComponent(BookingControls);
	fixture.componentRef.setInput('date', '2030-01-08');
	fixture.componentRef.setInput('room', room);
	fixture.detectChanges();
	return { fixture, root: fixture.nativeElement as HTMLElement };
}

describe('BookingControls (only Room 1 and Room 2 exist)', () => {
	it('offers exactly two rooms and checks the current one', () => {
		const { root } = render(2);
		const radios = [...root.querySelectorAll<HTMLInputElement>('input[type=radio]')];
		expect(radios.map((r) => r.value)).toEqual(['1', '2']);
		expect(radios.map((r) => r.checked)).toEqual([false, true]);
	});

	it('reports the room as a number when the student switches rooms', () => {
		const { fixture, root } = render(1);
		const rooms: unknown[] = [];
		fixture.componentInstance.roomChange.subscribe((room) => rooms.push(room));
		const second = root.querySelectorAll<HTMLInputElement>('input[type=radio]')[1];
		second.checked = true;
		second.dispatchEvent(new Event('change'));
		expect(rooms).toEqual([2]);
	});

	it('locks the date and both rooms while loading or saving, and unlocks them after', () => {
		const { fixture, root } = render();
		// :disabled is what the browser uses; radios inside <fieldset disabled> match it although their own
		// .disabled property stays false.
		const locked = () =>
			[
				root.querySelector('#booking-date')!,
				...root.querySelectorAll('input[type=radio]'),
			].map((el) => el.matches(':disabled'));
		expect(locked()).toEqual([false, false, false]);
		fixture.componentRef.setInput('disabled', true);
		fixture.detectChanges();
		expect(locked()).toEqual([true, true, true]);
		fixture.componentRef.setInput('disabled', false);
		fixture.detectChanges();
		expect(locked()).toEqual([false, false, false]);
	});

	it('shows the date as day-month-year, whatever the browser locale', () => {
		const { root } = render();
		expect(root.querySelector<HTMLInputElement>('#booking-date')?.value).toBe(
			'Tue, 08/01/2030',
		);
	});

	// The picker's own event is what a click on a calendar day produces.
	const pick = (fixture: ComponentFixture<BookingControls>, value: Date | null) =>
		(fixture.componentInstance as unknown as Picking).pick({ value });

	it('reports the picked weekday as yyyy-MM-dd', () => {
		const { fixture } = render();
		const dates: string[] = [];
		fixture.componentInstance.dateChange.subscribe((date) => dates.push(date));
		pick(fixture, new Date(2030, 0, 9));
		expect(dates).toEqual(['2030-01-09']);
	});

	it('ignores weekends and an emptied field', () => {
		const { fixture } = render();
		const dates: string[] = [];
		fixture.componentInstance.dateChange.subscribe((date) => dates.push(date));
		pick(fixture, new Date(2030, 0, 12));
		pick(fixture, new Date(2030, 0, 13));
		pick(fixture, null);
		expect(dates).toEqual([]);
	});

	it('only allows Monday to Friday', () => {
		const days = [7, 8, 9, 10, 11, 12, 13].map((d) => isWeekday(new Date(2030, 0, d)));
		expect(days).toEqual([true, true, true, true, true, false, false]);
		expect(isWeekday(null)).toBe(false);
	});

	it('limits the picker to the booking window', () => {
		const { fixture } = render();
		const { minDate, maxDate } = fixture.componentInstance as unknown as Picking;
		const days = (maxDate.getTime() - minDate.getTime()) / 86_400_000;
		expect(days).toBeGreaterThanOrEqual(89);
		expect(days).toBeLessThanOrEqual(91);
	});
});
