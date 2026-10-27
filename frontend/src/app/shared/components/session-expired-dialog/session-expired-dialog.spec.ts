import { TestBed } from '@angular/core/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { SessionExpiredDialog } from './session-expired-dialog';

describe('SessionExpiredDialog', () => {
	it('explains what happened and closes through its one Redirect button', () => {
		const close = vi.fn();
		TestBed.configureTestingModule({
			imports: [SessionExpiredDialog],
			providers: [{ provide: MatDialogRef, useValue: { close } }],
		});
		const fixture = TestBed.createComponent(SessionExpiredDialog);
		fixture.detectChanges();
		const root = fixture.nativeElement as HTMLElement;

		expect(root.textContent).toContain('Session expired');
		const buttons = root.querySelectorAll('button');
		expect(buttons).toHaveLength(1);
		expect(buttons[0].textContent?.trim()).toBe('Redirect');
		buttons[0].click();
		expect(close).toHaveBeenCalled();
	});
});
