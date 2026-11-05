import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { BookingsStore } from '../../../shared/stores/bookings-store';
import { NoticesService } from '../services/notices.service';
import { MyBookingsPage } from './my-bookings-page';

const NOTICE = { id: 'n1', message: 'Cancelled by staff: AC', created_at: '2030-01-01T00:00:00Z' };

describe('MyBookingsPage (shows messages from staff)', () => {
	function setup(list = vi.fn(() => of([NOTICE]))) {
		const api = { list, dismiss: vi.fn(() => of(undefined)) };
		const store = {
			appointments: signal([]),
			loaded: signal(true),
			error: signal(''),
			refresh: vi.fn(),
		};
		TestBed.overrideComponent(MyBookingsPage, {
			set: { providers: [{ provide: NoticesService, useValue: api }] },
		});
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{ provide: BookingsStore, useValue: store },
				{ provide: MatDialog, useValue: { open: vi.fn() } },
			],
		});
		const page = TestBed.createComponent(MyBookingsPage).componentInstance;
		// The page loads on open from an effect: run it.
		TestBed.tick();
		return { api, page, store };
	}

	it('loads the notices when it opens and hides one at once when it is dismissed', () => {
		const { api, page } = setup();
		expect(page.notices()).toEqual([NOTICE]);

		page.dismissNotice('n1');

		expect(page.notices()).toEqual([]);
		expect(api.dismiss).toHaveBeenCalledWith('n1');
	});

	it('says so when the notices cannot be loaded instead of staying silent', () => {
		const { page } = setup(vi.fn(() => throwError(() => new Error('down'))));

		expect(page.errorMessage()).toContain('messages from staff');
	});

	it('asks for the bookings and the notices when it opens', () => {
		const { api, store } = setup();

		expect(store.refresh).toHaveBeenCalled();
		expect(api.list).toHaveBeenCalledTimes(1);
	});

	it('does not bring back a notice dismissed while a list was on its way', () => {
		const answer = new Subject<(typeof NOTICE)[]>();
		const { page } = setup(vi.fn(() => answer));

		page.dismissNotice('n1');
		answer.next([NOTICE]);

		expect(page.notices()).toEqual([]);
	});
});
