import { nextBookableDay } from './jakarta-today';

describe('nextBookableDay (rooms open on weekdays only)', () => {
	it('keeps a weekday', () => {
		// 2030-01-07 is a Monday, 2030-01-11 a Friday.
		expect(nextBookableDay('2030-01-07')).toBe('2030-01-07');
		expect(nextBookableDay('2030-01-11')).toBe('2030-01-11');
	});

	it('moves Saturday and Sunday to Monday', () => {
		expect(nextBookableDay('2030-01-12')).toBe('2030-01-14');
		expect(nextBookableDay('2030-01-13')).toBe('2030-01-14');
	});

	it('crosses a month and year end', () => {
		// 2033-01-01 is a Saturday.
		expect(nextBookableDay('2033-01-01')).toBe('2033-01-03');
	});
});
