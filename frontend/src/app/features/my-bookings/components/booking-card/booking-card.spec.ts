import { TestBed } from '@angular/core/testing';
import { Appointment } from '../../../../core/types/appointment';
import { BookingCard } from './booking-card';

const appointment: Appointment = {
	id: 'b1',
	booker_id: 'u1',
	room_number: 2,
	start_time: '2030-01-08T02:00:00Z', // 09:00 in Jakarta (UTC+7)
	end_time: '2030-01-08T03:00:00Z',
	status: 'confirmed',
	sync_status: 'synced',
};

function render(value: Appointment, busy = false) {
	const fixture = TestBed.createComponent(BookingCard);
	fixture.componentRef.setInput('appointment', value);
	fixture.componentRef.setInput('busy', busy);
	fixture.detectChanges();
	return { fixture, root: fixture.nativeElement as HTMLElement };
}

describe('BookingCard (what a student sees for one booking)', () => {
	it('shows the date, room and the time range in WIB, not UTC', () => {
		const { root } = render(appointment);
		expect(root.querySelector('.date')?.textContent?.trim()).toBe('Tue 8 Jan');
		expect(root.querySelector('.time')?.textContent?.replace(/\s+/g, ' ')).toContain(
			'09:00–10:00 WIB',
		);
		expect(root.querySelector('.chip-orange')?.textContent).toContain('Room 2');
	});

	it('flags a booking whose Calendar sync failed, and only then', () => {
		expect(render(appointment).root.textContent).not.toContain('Calendar sync pending');
		const failed = render({ ...appointment, sync_status: 'failed' });
		expect(failed.root.textContent).toContain('Calendar sync pending');
	});

	const button = (root: HTMLElement, label: string) =>
		[...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === label)!;

	it('asks its parent to update or to cancel, depending on the button', () => {
		const { fixture, root } = render(appointment);
		const asked: string[] = [];
		fixture.componentInstance.updateRequested.subscribe(() => asked.push('update'));
		fixture.componentInstance.cancelRequested.subscribe(() => asked.push('cancel'));
		button(root, 'Update').click();
		button(root, 'Cancel').click();
		expect(asked).toEqual(['update', 'cancel']);
	});

	it('locks both buttons while a request for this booking is in flight', () => {
		const { root } = render(appointment, true);
		expect(button(root, 'Update').disabled).toBe(true);
		expect(button(root, 'Cancel').disabled).toBe(true);
	});
});
