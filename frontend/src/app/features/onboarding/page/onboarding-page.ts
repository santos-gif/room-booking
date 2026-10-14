import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MAJORS, Major } from '../../../core/types/auth';
import { OnboardingService } from '../services/onboarding.service';

@Component({
	providers: [OnboardingService],
	imports: [FormsModule],
	selector: 'app-onboarding-page',
	templateUrl: './onboarding-page.html',
	styleUrl: './onboarding-page.css',
})
export class OnboardingPage {
	private readonly onboardingService = inject(OnboardingService);
	private readonly router = inject(Router);
	readonly majors = MAJORS;
	readonly nim = signal<number | null>(null);
	readonly major = signal<Major | ''>('');
	readonly errorMessage = signal('');
	readonly submitting = signal(false);

	submit(): void {
		const nim = this.nim();
		const major = this.major();
		if (
			typeof nim !== 'number'
			|| !Number.isSafeInteger(nim)
			|| nim <= 0
			|| !major
		) {
			this.errorMessage.set('Enter a valid NIM and select your major.');
			return;
		}
		this.submitting.set(true);
		this.errorMessage.set('');
		this.onboardingService.saveOnboarding(nim, major).subscribe({
			next: () => void this.router.navigate(['/booking-form']),
			error: () => {
				this.errorMessage.set(
					'Unable to save your details. Please try again.',
				);
				this.submitting.set(false);
			},
		});
	}
}
