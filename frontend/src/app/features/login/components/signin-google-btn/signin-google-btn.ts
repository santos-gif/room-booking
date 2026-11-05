import { Component, input } from '@angular/core';

/** The Google button. It calls whatever the page hands it and never touches a service. */
@Component({
	selector: 'app-signin-google-btn',
	styleUrl: './signin-google-btn.css',
	templateUrl: './signin-google-btn.html',
})
export class SigninGoogleBtn {
	readonly action = input.required<() => void>();

	signIn(): void {
		this.action()();
	}
}
