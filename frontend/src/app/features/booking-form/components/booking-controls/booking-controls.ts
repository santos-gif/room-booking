import { Component, computed, input, output } from '@angular/core';
import {
	MAT_DATE_FORMATS,
	MAT_DATE_LOCALE,
	provideNativeDateAdapter,
} from '@angular/material/core';
import { MatDatepickerInputEvent, MatDatepickerModule } from '@angular/material/datepicker';
import { jakartaDate, jakartaToday } from '../../../../shared/helpers/jakarta-today';

const DAY_MS = 86_400_000;
/** Same limit as the server (slots.MAX_ADVANCE). */
const MAX_DAYS_AHEAD = 90;
/** Shown as "Tue, 08/01/2030": day first, whatever the browser locale. */
const DATE_FORMATS = {
	parse: { dateInput: null },
	display: {
		dateInput: { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' },
		monthYearLabel: { year: 'numeric', month: 'short' },
		dateA11yLabel: { year: 'numeric', month: 'long', day: 'numeric' },
		monthYearA11yLabel: { year: 'numeric', month: 'long' },
	},
};

const pad = (n: number): string => String(n).padStart(2, '0');

/** A yyyy-MM-dd string as a local-midnight Date (the picker works in local dates; no timezone shift). */
const toLocalDate = (value: string): Date => {
	const [year, month, day] = value.split('-').map(Number);
	return new Date(year, month - 1, day);
};

/** Rooms are bookable Monday to Friday. */
export const isWeekday = (date: Date | null): boolean => !!date && date.getDay() % 6 !== 0;

/** Date picker and room switch. Owns no state: the page passes values in and hears changes out. */
@Component({
	selector: 'app-booking-controls',
	imports: [MatDatepickerModule],
	providers: [
		provideNativeDateAdapter(),
		{ provide: MAT_DATE_LOCALE, useValue: 'en-GB' },
		{ provide: MAT_DATE_FORMATS, useValue: DATE_FORMATS },
	],
	templateUrl: './booking-controls.html',
	styleUrl: './booking-controls.css',
})
export class BookingControls {
	readonly date = input.required<string>();
	readonly room = input.required<1 | 2>();
	/** True while availability loads or a booking is saving: nothing here may be pressed then. */
	readonly disabled = input(false);
	readonly dateChange = output<string>();
	readonly roomChange = output<1 | 2>();
	protected readonly rooms = [1, 2] as const;
	protected readonly selected = computed(() => toLocalDate(this.date()));
	/** The bookable window: today through MAX_DAYS_AHEAD (Jakarta). */
	protected readonly minDate = toLocalDate(jakartaToday());
	protected readonly maxDate = toLocalDate(
		jakartaDate(new Date(Date.now() + MAX_DAYS_AHEAD * DAY_MS)),
	);
	protected readonly weekdaysOnly = isWeekday;

	protected pick(event: MatDatepickerInputEvent<Date>): void {
		const day = event.value;
		if (day && isWeekday(day)) {
			this.dateChange.emit(
				`${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`,
			);
		}
	}
}
