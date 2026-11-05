import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { Major } from '../../../core/types/auth';
import { ApiFailure, serverDetail } from '../../../core/utils/api-failure';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ProfileForm } from '../components/profile-form/profile-form';
import { OnboardingService } from '../services/onboarding.service';

/** The server refuses a NIM with more than 13 digits (the same cap as the backend payload). */
const MAX_NIM = 9_999_999_999_999;

type ProfileDraft = { nim: number | null; major: Major | '' };

@Component({
	providers: [OnboardingService],
	imports: [ProfileForm, AppHeader],
	selector: 'app-onboarding-page',
	templateUrl: './onboarding-page.html',
	styleUrl: './onboarding-page.css',
})
export class OnboardingPage {
	private readonly onboarding = inject(OnboardingService);
	private readonly router = inject(Router);
	readonly nim = signal<number | null>(null);
	readonly major = signal<Major | ''>('');
	private readonly submitError = signal('');
	readonly errorMessage = computed(
		() =>
			this.submitError() ||
			(this.profile.error()
				? 'Unable to load your profile. Reload the page to try again.'
				: ''),
	);
	readonly submitting = signal(false);
	// The same form edits the profile later (route data mode = 'edit'), e.g. when the major changes.
	readonly editing = inject(ActivatedRoute).snapshot.data['mode'] === 'edit';
	// What the server holds now, so "Save changes" only lights up once something differs.
	private readonly saved = signal<ProfileDraft | null>(null);
	readonly canSave = computed(() => {
		const details = this.details();
		if (!details || !this.editing) {
			return details !== null;
		}
		const saved = this.saved();
		return (
			saved !== null &&
			(saved.nim !== details.nim || saved.major !== details.major)
		);
	});

	// Only the Profile page (edit mode) loads the profile; onboarding starts with an empty form.
	private readonly profile = rxResource({
		params: () => this.editing || undefined,
		stream: () => this.onboarding.loadProfile(),
	});
	protected readonly fillForm = effect(() => {
		const user = this.profile.value();
		if (user) {
			untracked(() => {
				this.nim.set(user.nim);
				this.major.set(user.major ?? '');
				this.saved.set({ nim: user.nim, major: user.major ?? '' });
			});
		}
	});

	private details(): { nim: number; major: Major } | null {
		const nim = this.nim();
		const major = this.major();
		const valid =
			typeof nim === 'number' &&
			Number.isSafeInteger(nim) &&
			nim > 0 &&
			nim <= MAX_NIM &&
			major !== '';
		return valid ? { nim, major } : null;
	}

	submit(): void {
		const details = this.details();
		if (!details) {
			this.submitError.set('Enter a valid NIM/NIDN and select your major.');
			return;
		}
		this.submitting.set(true);
		this.submitError.set('');
		this.onboarding.saveOnboarding(details.nim, details.major).subscribe({
			next: () => void this.router.navigate(['/my-bookings']),
			error: (error: ApiFailure) => {
				// 409: that NIM belongs to another student, and the server's own sentence says so.
				const reason = error.status === 409 ? serverDetail(error) : null;
				this.submitError.set(
					reason ?? 'Unable to save your details. Please try again.',
				);
				this.submitting.set(false);
			},
		});
	}
}
