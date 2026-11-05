import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { StaffService } from '../services/staff.service';
import { StaffPage } from './staff-page';

const ROW = {
	appointment_id: 'a1',
	booker_name: 'Santos',
	booker_nim: 2510101051,
	booker_email: 's@student.pradita.ac.id',
	room_number: 1,
	start_time: '2030-01-02T02:00:00Z',
	end_time: '2030-01-02T03:00:00Z',
};
const PAYLOAD = {
	room_number: 1 as const,
	start_date: '2030-01-01',
	end_date: '2030-01-03',
	reason: 'AC',
};

describe('StaffPage (owns the state of both panels)', () => {
	function setup(overrides: Partial<Record<string, unknown>> = {}) {
		const api = {
			closures: vi.fn(() => of([])),
			preview: vi.fn(() => of([ROW])),
			createClosure: vi.fn(() => of({ cancelled: 1, events_left: 0 })),
			deleteClosure: vi.fn(() => of(undefined)),
			holder: vi.fn(() => of([ROW])),
			override: vi.fn(() => of({ cancelled: 1, events_left: 2 })),
			...overrides,
		};
		TestBed.overrideComponent(StaffPage, {
			set: { providers: [{ provide: StaffService, useValue: api }] },
		});
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{ provide: MatDialog, useValue: { open: vi.fn() } },
			],
		});
		return { api, page: TestBed.createComponent(StaffPage).componentInstance };
	}

	it('closes the room after a preview, says what happened and forgets the preview', () => {
		const { api, page } = setup();

		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });
		expect(page.affected()).toHaveLength(1);
		page.close(PAYLOAD);

		expect(api.createClosure).toHaveBeenCalledWith(PAYLOAD);
		expect(page.closureMessage()).toContain('1 booking(s) cancelled');
		expect(page.affected()).toBeNull();
	});

	it('forgets a preview or a check when the panel says its form changed', () => {
		const { page } = setup();
		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });
		page.check({ room: 1, startTime: '2030-01-08T09:00:00+07:00' });

		page.forgetPreview();
		page.forgetCheck();

		expect(page.affected()).toBeNull();
		expect(page.holders()).toBeNull();
	});

	it('takes a slot and mentions the calendar events left for tonight', () => {
		const { page } = setup();

		page.take({
			room_number: 1,
			start_time: '2030-01-08T09:00:00+07:00',
			reason: 'Defence',
		});

		expect(page.overrideMessage()).toContain(
			'2 calendar event(s) will be removed tonight',
		);
		expect(page.holders()).toBeNull();
	});

	it('shows the server sentence when a request fails and releases the buttons', () => {
		const { page } = setup({
			preview: vi.fn(() =>
				throwError(() => ({
					status: 403,
					error: { detail: 'Staff only.' },
				})),
			),
		});

		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });

		expect(page.closureError()).toBe('Staff only.');
		expect(page.affected()).toBeNull();
		expect(page.closureBusy()).toBe(false);
	});

	it('ignores a preview that answers after the dates were edited', () => {
		const answer = new Subject<unknown[]>();
		const { page } = setup({ preview: vi.fn(() => answer) });

		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });
		page.forgetPreview();
		answer.next([ROW]);

		expect(page.affected()).toBeNull();
		expect(page.closureBusy()).toBe(false);
	});

	it('keeps each panel busy until its own last request answers', () => {
		const slow = new Subject<unknown[]>();
		const { page } = setup({ holder: vi.fn(() => slow) });

		page.check({ room: 1, startTime: '2030-01-08T09:00:00+07:00' });
		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });

		expect(page.overrideBusy()).toBe(true);
		expect(page.closureBusy()).toBe(false);
		slow.next([]);
		slow.complete();
		expect(page.overrideBusy()).toBe(false);
	});

	it('clears an old error when the form is edited', () => {
		const { page } = setup({
			preview: vi.fn(() =>
				throwError(() => ({
					status: 403,
					error: { detail: 'Staff only.' },
				})),
			),
		});
		page.preview({ room: 1, start: '2030-01-01', end: '2030-01-03' });

		page.forgetPreview();

		expect(page.closureError()).toBe('');
	});
});
