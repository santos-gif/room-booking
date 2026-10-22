import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

bootstrapApplication(App, appConfig).catch((err) => {
	console.error(err);
	// Replace the boot spinner so a failed download never spins forever.
	const root = document.querySelector('app-root');
	if (root) {
		root.innerHTML =
			'<div class="loading-center"><p class="boot-error">The app could not start. <a href="/">Reload</a></p></div>';
	}
});
