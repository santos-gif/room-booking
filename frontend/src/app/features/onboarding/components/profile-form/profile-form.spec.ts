import { TestBed } from '@angular/core/testing';
import { ProfileForm } from './profile-form';

function render(inputs: Record<string, unknown>) {
	const fixture = TestBed.createComponent(ProfileForm);
	for (const [name, value] of Object.entries(inputs)) {
		fixture.componentRef.setInput(name, value);
	}
	fixture.detectChanges();
	const root = fixture.nativeElement as HTMLElement;
	return { fixture, button: root.querySelector<HTMLButtonElement>('button[type=submit]')! };
}

describe('ProfileForm (Save only lights up when there is something to save)', () => {
	it('keeps the submit button disabled until the page says the form can be saved', () => {
		expect(render({ canSubmit: false }).button.disabled).toBe(true);
		expect(render({ canSubmit: true }).button.disabled).toBe(false);
	});

	it('stays disabled while a save is in flight, even when valid', () => {
		expect(render({ canSubmit: true, submitting: true }).button.disabled).toBe(true);
	});

	it('words the button for first-time setup, editing and saving', () => {
		expect(render({ canSubmit: true }).button.textContent?.trim()).toBe('Continue');
		expect(render({ canSubmit: true, editing: true }).button.textContent?.trim()).toBe(
			'Save changes',
		);
		expect(
			render({ canSubmit: true, submitting: true }).button.textContent?.trim(),
		).toBe('Saving…');
	});

	it('offers every approved major, starting with Information Technology', () => {
		const { fixture } = render({});
		const options = [
			...(fixture.nativeElement as HTMLElement).querySelectorAll('select option'),
		].map((o) => o.textContent?.trim());
		expect(options[0]).toBe('Select your major');
		expect(options).toContain('Information Technology');
		expect(options).not.toContain('IT');
	});
});
