import { ApplicationConfig, ErrorHandler, provideBrowserGlobalErrorListeners } from '@angular/core';
import { PreloadAllModules, provideRouter, withPreloading } from '@angular/router';

import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { apiCookieInterceptor } from './core/interceptors/api-cookie.interceptor';
import { authRefreshInterceptor } from './core/interceptors/auth-refresh-interceptor';
import { serverErrorInterceptor } from './core/interceptors/server-error-interceptor';
import { ClientErrorHandler } from './core/handlers/client-error-handler';

export const appConfig: ApplicationConfig = {
	providers: [
		provideBrowserGlobalErrorListeners(),
		provideRouter(routes, withPreloading(PreloadAllModules)),
		provideHttpClient(
			withInterceptors([
				apiCookieInterceptor,
				authRefreshInterceptor,
				serverErrorInterceptor,
			]),
		),
		{
			provide: ErrorHandler,
			useClass: ClientErrorHandler,
		},
	],
};
