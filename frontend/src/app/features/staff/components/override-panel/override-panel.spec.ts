import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { StaffService } from '../../service/staff.service';
import { OverridePanel } from './override-panel';

describe('OverridePanel (take one slot: check first, then take)', () => {
	function setup(holders: unknown[] = []) {
		const api = {
			holder: vi.fn(() => of(holders)),
			override: vi.fn(() => of({ cancelled: holders.length, events_left: 0 })),
		};
		TestBed.configureTestingModule({
			providers: [{ provide: StaffService, useValue: api }],
		});
		const panel = TestBed.createComponent(OverridePanel).componentInstance;
		panel.edit(panel.day, '2030-01-08');
		panel.edit(panel.hour, 9);
		return { api, panel };
	}

	it('asks about the slot in Jakarta time and takes it with the reason', () => {
		const { api, panel } = setup([{ appointment_id: 'a1' }]);

		panel.check();
		panel.reason.set('Thesis defence');
		panel.take();

		expect(api.holder).toHaveBeenCalledWith(1, '2030-01-08T09:00:00+07:00');
		expect(api.override).toHaveBeenCalledWith({
			room_number: 1,
			start_time: '2030-01-08T09:00:00+07:00',
			reason: 'Thesis defence',
		});
		expect(panel.message()).toContain('1 booking(s) cancelled');
		expect(panel.holders()).toBeNull();
	});

	it('forgets the check when the slot changes, so the wrong slot can never be taken', () => {
		const { panel } = setup();
		panel.check();
		expect(panel.holders()).toEqual([]);

		panel.edit(panel.hour, 10);

		expect(panel.holders()).toBeNull();
	});
});
