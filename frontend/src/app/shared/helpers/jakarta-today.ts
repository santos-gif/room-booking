/** A moment's calendar date in Jakarta as yyyy-MM-dd (what the date picker and the availability API expect). */
export function jakartaDate(at: Date): string {
	const parts = new Intl.DateTimeFormat('en-CA', {
		timeZone: 'Asia/Jakarta',
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
	}).formatToParts(at);
	const part = (type: string): string =>
		parts.find((item) => item.type === type)?.value ?? '';
	return `${part('year')}-${part('month')}-${part('day')}`;
}

export const jakartaToday = (): string => jakartaDate(new Date());

/** Rooms are bookable on weekdays only: today (Jakarta) if it is one, otherwise the coming Monday. */
export function nextBookableDay(today: string = jakartaToday()): string {
	const [year, month, day] = today.split('-').map(Number);
	const date = new Date(Date.UTC(year, month - 1, day));
	const weekday = date.getUTCDay();
	if (weekday === 0 || weekday === 6) {
		date.setUTCDate(date.getUTCDate() + (weekday === 6 ? 2 : 1));
	}
	return date.toISOString().slice(0, 10);
}
