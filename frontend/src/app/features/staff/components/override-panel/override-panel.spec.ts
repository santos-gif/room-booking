import { TestBed } from '@angular/core/testing';
import { OverridePanel } from './override-panel';

describe('OverridePanel (asks the page; never calls a service)', () => {
	function setup() {
		const panel = TestBed.createComponent(OverridePanel).componentInstance;
		panel.edit(panel.day, '2030-01-08');
		panel.edit(panel.hour, 9);
		return panel;
	}

	it('asks about the slot in Jakarta time and takes it with the reason', () => {
		const panel = setup();
		const check = vi.fn();
		const take = vi.fn();
		panel.checkRequested.subscribe(check);
		panel.takeRequested.subscribe(take);

		panel.check();
		panel.reason.set('Thesis defence');
		panel.take();

		expect(check).toHaveBeenCalledWith({
			room: 1,
			startTime: '2030-01-08T09:00:00+07:00',
		});
		expect(take).toHaveBeenCalledWith({
			room_number: 1,
			start_time: '2030-01-08T09:00:00+07:00',
			reason: 'Thesis defence',
		});
	});

	it('says so when the slot changes, so the page forgets the check', () => {
		const panel = setup();
		const edited = vi.fn();
		panel.edited.subscribe(edited);

		panel.edit(panel.hour, 10);

		expect(edited).toHaveBeenCalledTimes(1);
	});
});
