import { TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { SessionExpiredDialog } from './session-expired-dialog';

function render(reconnect: boolean) {
	const close = vi.fn();
	TestBed.configureTestingModule({
		imports: [SessionExpiredDialog],
		providers: [
			{ provide: MatDialogRef, useValue: { close } },
			{ provide: MAT_DIALOG_DATA, useValue: { reconnect } },
		],
	});
	const fixture = TestBed.createComponent(SessionExpiredDialog);
	fixture.detectChanges();
	return { close, root: fixture.nativeElement as HTMLElement };
}

describe('SessionExpiredDialog', () => {
	it('explains what happened and closes through its one Redirect button', () => {
		const { close, root } = render(false);

		expect(root.textContent).toContain('Session expired');
		const buttons = root.querySelectorAll('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0].textContent?.trim()).toBe('Redirect');
		buttons[0].click();
		expect(close).toHaveBeenCalled();
	});

	it('asks to reconnect when Google no longer accepts the Calendar connection', () => {
		const { close, root } = render(true);

		expect(root.textContent).toContain('Google Calendar disconnected');
		const buttons = root.querySelectorAll('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0].textContent?.trim()).toBe('Reconnect');
		buttons[0].click();
		expect(close).toHaveBeenCalled();
	});
});
