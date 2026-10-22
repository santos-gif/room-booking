import { Component, input, output } from '@angular/core';

/** Outcome of a booking attempt. Offers a Calendar reconnect when Google rejected the token. */
@Component({
	selector: 'app-result-dialog',
	templateUrl: './result-dialog.html',
	styleUrl: './result-dialog.css',
})
export class ResultDialog {
	readonly message = input.required<string>();
	readonly reconnectNeeded = input(false);
	readonly reconnect = output<void>();
	readonly closed = output<void>();
}
