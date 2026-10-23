import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

const REASONS: Record<string, string> = {
	university_email_required:
		'This app is only for Pradita accounts. Sign in with your @student.pradita.ac.id or @pradita.ac.id email.',
	verified_email_required:
		'Google could not confirm that this email address is verified. Verify it with Google, then sign in again.',
	account_link_required:
		'Your booking profile has to be linked by an administrator before you can sign in. Please contact them.',
};
const FALLBACK = 'This account does not have access to Discussion Room Booking.';

/** Shown instead of a form error when a sign-in is refused, so the student sees a clear answer. */
@Component({
	imports: [RouterLink],
	selector: 'app-access-denied-page',
	templateUrl: './access-denied-page.html',
	styleUrl: './access-denied-page.css',
})
export class AccessDeniedPage {
	protected readonly message = this.messageFor(
		inject(ActivatedRoute).snapshot.queryParamMap.get('reason') ?? '',
	);

	// hasOwn: ?reason=constructor must not find Object's own members.
	private messageFor(reason: string): string {
		return Object.hasOwn(REASONS, reason) ? REASONS[reason] : FALLBACK;
	}
}
