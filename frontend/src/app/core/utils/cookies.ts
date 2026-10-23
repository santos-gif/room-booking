/** Value of a cookie, or null. Matches the whole name, so `x_csrf_token` never answers for `csrf_token`. */
export function readCookie(name: string): string | null {
	const prefix = `${name}=`;
	const cookie = document.cookie.split('; ').find((item) => item.startsWith(prefix));
	return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

export const hasCookie = (name: string): boolean => readCookie(name) !== null;
