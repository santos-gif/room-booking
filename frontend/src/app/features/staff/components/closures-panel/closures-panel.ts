import { DatePipe } from '@angular/common';
import { Component, computed, input, output, signal, WritableSignal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Closure, ClosurePayload, ClosureQuery, StaffBooking } from '../../types/staff';

/** The close-a-room form and what the page answers; it never calls a service, the page does. */
@Component({
	imports: [DatePipe, FormsModule],
	selector: 'app-closures-panel',
	templateUrl: './closures-panel.html',
	styleUrl: './closures-panel.css',
})
export class ClosuresPanel {
	readonly closures = input<Closure[]>([]);
	/** True until the first list arrives (a reload after a change keeps showing the old list). */
	readonly loading = input(false);
	/** Null until previewed: the close button needs a preview of exactly these dates. */
	readonly affected = input<StaffBooking[] | null>(null);
	readonly busy = input(false);
	readonly message = input('');
	readonly error = input('');
	/** Any change to the form: the page forgets the preview. */
	readonly edited = output<void>();
	readonly previewRequested = output<ClosureQuery>();
	readonly closeRequested = output<ClosurePayload>();
	readonly reopenRequested = output<Closure>();
	readonly room = signal<1 | 2>(1);
	readonly start = signal('');
	readonly end = signal('');
	readonly reason = signal('');
	readonly ready = computed(
		() =>
			!!this.start() &&
			!!this.end() &&
			this.end() >= this.start() &&
			!!this.reason().trim(),
	);
	/** A closure of this room that already covers a chosen day (ISO dates compare correctly as text). */
	readonly clash = computed(() => {
		const [room, start, end] = [this.room(), this.start(), this.end()];
		const found = this.closures().find(
			(c) => c.room_number === room && c.start_date <= end && c.end_date >= start,
		);
		return start && end && end >= start ? (found ?? null) : null;
	});

	edit<T>(target: WritableSignal<T>, value: T): void {
		target.set(value);
		this.edited.emit();
	}

	preview(): void {
		this.previewRequested.emit({
			room: this.room(),
			start: this.start(),
			end: this.end(),
		});
	}

	close(): void {
		this.closeRequested.emit({
			room_number: this.room(),
			start_date: this.start(),
			end_date: this.end(),
			reason: this.reason().trim(),
		});
	}

	remove(closure: Closure): void {
		this.reopenRequested.emit(closure);
	}
}
