import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { readCookie } from '../utils/cookies';

export const apiCookieInterceptor: HttpInterceptorFn = (request, next) => {
	if (
		environment.apiUrl &&
		(request.url === environment.apiUrl ||
			request.url.startsWith(`${environment.apiUrl}/`))
	) {
		const unsafeMethod = !['GET', 'HEAD', 'OPTIONS'].includes(request.method);
		const csrfToken = unsafeMethod ? readCookie('csrf_token') : null;
		const headers = csrfToken
			? request.headers.set('X-CSRF-Token', csrfToken)
			: request.headers;
		return next(request.clone({ withCredentials: true, headers }));
	}

	return next(request);
};
