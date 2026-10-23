import { hasCookie, readCookie } from './cookies';

describe('cookies', () => {
	afterEach(() => {
		document.cookie = 'csrf_token=; max-age=0';
		document.cookie = 'x_csrf_token=; max-age=0';
	});

	it('finds a cookie by its exact name', () => {
		document.cookie = 'csrf_token=a%20b';
		expect(readCookie('csrf_token')).toBe('a b');
		expect(hasCookie('csrf_token')).toBe(true);
	});

	it('is not fooled by a cookie whose name only ends the same way', () => {
		document.cookie = 'x_csrf_token=evil';
		expect(hasCookie('csrf_token')).toBe(false);
		expect(readCookie('csrf_token')).toBeNull();
	});
});
