import { TestBed } from '@angular/core/testing';
import { SigninGoogleBtn } from './signin-google-btn';

describe('SigninGoogleBtn (runs the action the page gives it)', () => {
	it('calls the action on click and needs no service', () => {
		const action = vi.fn();
		const fixture = TestBed.createComponent(SigninGoogleBtn);
		fixture.componentRef.setInput('action', action);
		fixture.detectChanges();

		fixture.nativeElement.querySelector('#google-signin-btn').click();

		expect(action).toHaveBeenCalledTimes(1);
	});
});
