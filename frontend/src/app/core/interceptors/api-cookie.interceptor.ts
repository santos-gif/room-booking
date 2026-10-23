import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export const apiCookieInterceptor: HttpInterceptorFn = (request, next) => {
	if (environment.apiUrl && (request.url === environment.apiUrl || request.url.startsWith(`${environment.apiUrl}/`))) {
		const unsafeMethod = !['GET', 'HEAD', 'OPTIONS'].includes(request.method);
		const csrfToken = unsafeMethod ? readCookie('csrf_token') : null;
		const headers = csrfToken
			? request.headers.set('X-CSRF-Token', csrfToken)
			: request.headers;
		return next(request.clone({ withCredentials: true, headers }));
	}

	return next(request);
};

function readCookie(name: string): string | null {
	const prefix = `${name}=`;
	const cookie = document.cookie
		.split('; ')
		.find((item) => item.startsWith(prefix));
	return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}
