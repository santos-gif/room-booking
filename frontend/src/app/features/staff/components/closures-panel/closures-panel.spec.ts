import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { of, throwError } from 'rxjs';
import { StaffService } from '../../service/staff.service';
import { ClosuresPanel } from './closures-panel';

const ROW = {
	appointment_id: 'a1',
	booker_name: 'Santos',
	booker_nim: 2510101051,
	booker_email: 's@student.pradita.ac.id',
	room_number: 1,
	start_time: '2030-01-02T02:00:00Z',
	end_time: '2030-01-02T03:00:00Z',
};

describe('ClosuresPanel (a room closes only after a preview of exactly these dates)', () => {
	function setup(overrides: Partial<Record<string, unknown>> = {}) {
		const api = {
			closures: vi.fn(() => of([])),
			preview: vi.fn(() => of([ROW])),
			createClosure: vi.fn(() => of({ cancelled: 1, events_left: 0 })),
			deleteClosure: vi.fn(() => of(undefined)),
			...overrides,
		};
		TestBed.configureTestingModule({
			providers: [
				{ provide: StaffService, useValue: api },
				{ provide: MatDialog, useValue: { open: vi.fn() } },
			],
		});
		const panel = TestBed.createComponent(ClosuresPanel).componentInstance;
		panel.edit(panel.start, '2030-01-01');
		panel.edit(panel.end, '2030-01-03');
		panel.edit(panel.reason, 'AC repair');
		return { api, panel };
	}

	it('previews who is affected, then closes the room and says what happened', () => {
		const { api, panel } = setup();

		panel.preview();
		expect(panel.affected()).toHaveLength(1);
		panel.close();

		expect(api.createClosure).toHaveBeenCalledWith({
			room_number: 1,
			start_date: '2030-01-01',
			end_date: '2030-01-03',
			reason: 'AC repair',
		});
		expect(panel.message()).toContain('1 booking(s) cancelled');
		expect(panel.affected()).toBeNull();
	});

	it('forgets the preview as soon as the form changes', () => {
		const { panel } = setup();
		panel.preview();

		panel.edit(panel.end, '2030-01-09');

		expect(panel.affected()).toBeNull();
	});

	it('is not ready for backwards dates or an empty reason', () => {
		const { panel } = setup();
		expect(panel.ready()).toBe(true);
		panel.edit(panel.end, '2029-12-31');
		expect(panel.ready()).toBe(false);
		panel.edit(panel.end, '2030-01-03');
		panel.edit(panel.reason, '  ');
		expect(panel.ready()).toBe(false);
	});

	it('shows the server sentence when the request fails and keeps nothing half-done', () => {
		const { panel } = setup({
			preview: vi.fn(() =>
				throwError(() => ({
					status: 403,
					error: { detail: 'Staff only.' },
				})),
			),
		});

		panel.preview();

		expect(panel.error()).toBe('Staff only.');
		expect(panel.affected()).toBeNull();
		expect(panel.busy()).toBe(false);
	});
});
