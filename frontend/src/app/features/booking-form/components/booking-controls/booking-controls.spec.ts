import { TestBed } from '@angular/core/testing';
import { BookingControls } from './booking-controls';

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

	it('shows the date as day-month-year, whatever the browser locale', () => {
		const { root } = render();
		expect(root.querySelector('.date-text')?.textContent?.trim()).toBe(
			'Tue, 08-01-2030',
		);
	});

	it('reports the picked date', () => {
		const { fixture, root } = render();
		const dates: string[] = [];
		fixture.componentInstance.dateChange.subscribe((date) => dates.push(date));
		const picker = root.querySelector<HTMLInputElement>('#booking-date')!;
		expect(picker.value).toBe('2030-01-08');
		picker.value = '2030-01-09';
		picker.dispatchEvent(new Event('change'));
		expect(dates).toEqual(['2030-01-09']);
	});
});
