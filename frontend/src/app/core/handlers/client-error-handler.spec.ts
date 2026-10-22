import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { ClientErrorHandler } from './client-error-handler';

describe('ClientErrorHandler (an unexpected error never traps the student)', () => {
	function setup() {
		const open: unknown[] = [];
		const dialog = {
			openDialogs: open,
			open: vi.fn((_component: unknown, config: { disableClose?: boolean }) => {
				open.push(config);
			}),
		};
		TestBed.configureTestingModule({
			providers: [ClientErrorHandler, { provide: MatDialog, useValue: dialog }],
		});
		vi.spyOn(console, 'error').mockImplementation(() => undefined);
		return { handler: TestBed.inject(ClientErrorHandler), dialog };
	}

	it('shows a notice the student can close (no forced reload)', () => {
		const { handler, dialog } = setup();
		handler.handleError(new Error('boom'));
		expect(dialog.open).toHaveBeenCalledTimes(1);
		expect(dialog.open.mock.calls[0][1].disableClose).toBeUndefined();
	});

	it('shows only one notice at a time, however many errors arrive', () => {
		const { handler, dialog } = setup();
		handler.handleError(new Error('first'));
		handler.handleError(new Error('second'));
		handler.handleError('third');
		expect(dialog.open).toHaveBeenCalledTimes(1);
	});

	it('ignores the harmless ResizeObserver browser notice', () => {
		const { handler, dialog } = setup();
		handler.handleError(
			new Error('ResizeObserver loop completed with undelivered notifications.'),
		);
		expect(dialog.open).not.toHaveBeenCalled();
	});

	it('does not show a dialog for a failed lazy page (it reloads instead)', () => {
		const { handler, dialog } = setup();
		sessionStorage.setItem('chunk-reload-at', String(Date.now())); // already reloaded just now: no loop
		handler.handleError(
			new Error('Failed to fetch dynamically imported module: /chunk-ABC.js'),
		);
		expect(dialog.open).not.toHaveBeenCalled();
	});
});
