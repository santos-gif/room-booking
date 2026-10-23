import { A11yModule } from '@angular/cdk/a11y';
import { Component, input, output } from '@angular/core';

/**
 * Outcome of a booking attempt. Offers a Calendar reconnect when Google rejected the token.
 * Keyboard and screen readers: focus moves into it and stays there, Escape closes it, and focus
 * returns to where it was (the CDK focus trap does all three).
 */
@Component({
	selector: 'app-result-dialog',
	imports: [A11yModule],
	templateUrl: './result-dialog.html',
	styleUrl: './result-dialog.css',
})
export class ResultDialog {
	readonly message = input.required<string>();
	readonly reconnectNeeded = input(false);
	readonly reconnect = output<void>();
	readonly closed = output<void>();
}
