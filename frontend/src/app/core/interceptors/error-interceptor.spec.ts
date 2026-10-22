import { HttpErrorResponse, HttpRequest, HttpResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { Observable, throwError } from 'rxjs';
import { serverErrorInterceptor } from './server-error-interceptor';

describe('serverErrorInterceptor (at most one dialog, never for the availability poll)', () => {
	function call(url: string, status: number, openDialogs: unknown[] = []) {
		const dialog = { openDialogs, open: vi.fn() };
		TestBed.configureTestingModule({
			providers: [{ provide: MatDialog, useValue: dialog }],
		});
		const next = () =>
			throwError(() => new HttpErrorResponse({ status, url })) as Observable<
				HttpResponse<unknown>
			>;
		TestBed.runInInjectionContext(() =>
			serverErrorInterceptor(new HttpRequest('GET', url), next),
		).subscribe({ error: () => undefined });
		return dialog;
	}

	it('opens a dialog for a server error or a lost connection', () => {
		expect(call('/api/v1/appointments/', 500).open).toHaveBeenCalledTimes(1);
		TestBed.resetTestingModule();
		expect(call('/api/v1/appointments/', 0).open).toHaveBeenCalledTimes(1);
	});

	it('does not open a second dialog while one is already showing', () => {
		expect(call('/api/v1/appointments/', 500, [{}]).open).not.toHaveBeenCalled();
	});

	it('stays quiet for the availability poll (the page shows its own message)', () => {
		expect(call('/api/v1/appointments/availability', 503).open).not.toHaveBeenCalled();
	});

	it('does not open a dialog for ordinary client errors', () => {
		expect(call('/api/v1/appointments/', 409).open).not.toHaveBeenCalled();
	});
});
