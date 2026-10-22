import { TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { ConfirmDialog, ConfirmDialogData } from './confirm-dialog';

const data: ConfirmDialogData = {
	title: 'Cancel this booking?',
	message: 'The slot is freed for other students.',
	confirmLabel: 'Cancel booking',
	cancelLabel: 'Keep booking',
};

describe('ConfirmDialog (a destructive action always asks first)', () => {
	function render() {
		const close = vi.fn();
		TestBed.configureTestingModule({
			providers: [
				{ provide: MAT_DIALOG_DATA, useValue: data },
				{ provide: MatDialogRef, useValue: { close } },
			],
		});
		const fixture = TestBed.createComponent(ConfirmDialog);
		fixture.detectChanges();
		const buttons = [
			...(fixture.nativeElement as HTMLElement).querySelectorAll('button'),
		];
		return { fixture, buttons, close };
	}

	it('shows the question and both answers in the caller’s words', () => {
		const { fixture, buttons } = render();
		const text = (fixture.nativeElement as HTMLElement).textContent;
		expect(text).toContain('Cancel this booking?');
		expect(text).toContain('The slot is freed for other students.');
		expect(buttons.map((b) => b.textContent?.trim())).toEqual([
			'Keep booking',
			'Cancel booking',
		]);
	});

	it('answers false for the safe button and true for the destructive one', () => {
		const { buttons, close } = render();
		buttons[0].click();
		expect(close).toHaveBeenLastCalledWith(false);
		buttons[1].click();
		expect(close).toHaveBeenLastCalledWith(true);
	});
});
