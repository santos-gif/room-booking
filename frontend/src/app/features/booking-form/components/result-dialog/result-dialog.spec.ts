import { TestBed } from '@angular/core/testing';
import { ResultDialog } from './result-dialog';

describe('ResultDialog (usable without a mouse)', () => {
	function render(reconnectNeeded = false) {
		const fixture = TestBed.createComponent(ResultDialog);
		fixture.componentRef.setInput('message', 'Appointment booked successfully.');
		fixture.componentRef.setInput('reconnectNeeded', reconnectNeeded);
		fixture.detectChanges();
		return { fixture, root: fixture.nativeElement as HTMLElement };
	}

	it('is announced as a modal dialog showing the message', () => {
		const dialog = render().root.querySelector('[role=dialog]')!;
		expect(dialog.getAttribute('aria-modal')).toBe('true');
		expect(dialog.textContent).toContain('Appointment booked successfully.');
	});

	it('closes on Escape and on Continue', () => {
		const { fixture, root } = render();
		let closed = 0;
		fixture.componentInstance.closed.subscribe(() => closed++);
		root
			.querySelector('[role=dialog]')!
			.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		root.querySelector<HTMLButtonElement>('.btn-primary')!.click();
		expect(closed).toBe(2);
	});

	it('offers the Calendar reconnect only when Google rejected the token', () => {
		expect(render(false).root.textContent).not.toContain('Reconnect Google Calendar');
		TestBed.resetTestingModule();
		expect(render(true).root.textContent).toContain('Reconnect Google Calendar');
	});
});
