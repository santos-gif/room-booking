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
