import { Component, input, model, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MAJORS, Major } from '../../../../core/types/auth';

/** NIM and major fields, used for first-time onboarding and later profile edits. */
@Component({
	selector: 'app-profile-form',
	imports: [FormsModule],
	templateUrl: './profile-form.html',
	styleUrl: './profile-form.css',
})
export class ProfileForm {
	readonly nim = model<number | null>(null);
	readonly major = model<Major | ''>('');
	readonly editing = input(false);
	readonly canSubmit = input(false);
	readonly submitting = input(false);
	readonly errorMessage = input('');
	readonly submitted = output<void>();
	protected readonly majors = MAJORS;
}
