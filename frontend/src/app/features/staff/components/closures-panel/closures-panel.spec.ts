import { TestBed } from '@angular/core/testing';
import { ClosuresPanel } from './closures-panel';

describe('ClosuresPanel (asks the page; never calls a service)', () => {
	function setup() {
		const fixture = TestBed.createComponent(ClosuresPanel);
		const panel = fixture.componentInstance;
		panel.edit(panel.start, '2030-01-01');
		panel.edit(panel.end, '2030-01-03');
		panel.edit(panel.reason, 'AC repair');
		return panel;
	}

	it('asks the page to preview the dates it shows', () => {
		const panel = setup();
		const asked = vi.fn();
		panel.previewRequested.subscribe(asked);

		panel.preview();

		expect(asked).toHaveBeenCalledWith({
			room: 1,
			start: '2030-01-01',
			end: '2030-01-03',
		});
	});

	it('asks the page to close the room with a trimmed reason', () => {
		const panel = setup();
		const asked = vi.fn();
		panel.closeRequested.subscribe(asked);
		panel.edit(panel.reason, ' AC repair ');

		panel.close();

		expect(asked).toHaveBeenCalledWith({
			room_number: 1,
			start_date: '2030-01-01',
			end_date: '2030-01-03',
			reason: 'AC repair',
		});
	});

	it('says so as soon as the form changes, so the page can forget the preview', () => {
		const panel = setup();
		const edited = vi.fn();
		panel.edited.subscribe(edited);

		panel.edit(panel.end, '2030-01-09');

		expect(edited).toHaveBeenCalledTimes(1);
	});

	it('is not ready for backwards dates or an empty reason', () => {
		const panel = setup();
		expect(panel.ready()).toBe(true);
		panel.edit(panel.end, '2029-12-31');
		expect(panel.ready()).toBe(false);
		panel.edit(panel.end, '2030-01-03');
		panel.edit(panel.reason, '  ');
		expect(panel.ready()).toBe(false);
	});

	it('points at the closure that already covers a chosen day, only for that room', () => {
		const fixture = TestBed.createComponent(ClosuresPanel);
		const panel = fixture.componentInstance;
		const existing = {
			id: 'c1',
			room_number: 1 as const,
			start_date: '2030-01-02',
			end_date: '2030-01-05',
			reason: 'AC',
		};
		fixture.componentRef.setInput('closures', [existing]);
		panel.edit(panel.start, '2030-01-05');
		panel.edit(panel.end, '2030-01-08');

		expect(panel.clash()).toEqual(existing);

		panel.edit(panel.start, '2030-01-06');
		expect(panel.clash()).toBeNull();
		panel.edit(panel.start, '2030-01-01');
		panel.edit(panel.room, 2);
		expect(panel.clash()).toBeNull();
	});
});
