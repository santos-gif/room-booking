import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
	NavigationCancel,
	NavigationEnd,
	NavigationError,
	NavigationStart,
	Router,
	RouterOutlet,
} from '@angular/router';
import { filter, map } from 'rxjs';

@Component({
	selector: 'app-root',
	imports: [RouterOutlet],
	templateUrl: './app.html',
	styleUrl: './app.css',
})
export class App {
	// True from startup until the first navigation ends, and during every later one, so a slow
	// route guard (a cold backend answering /auth/me) never looks like a blank page.
	protected readonly navigating = toSignal(
		inject(Router).events.pipe(
			filter(
				(event) =>
					event instanceof NavigationStart ||
					event instanceof NavigationEnd ||
					event instanceof NavigationCancel ||
					event instanceof NavigationError,
			),
			map((event) => event instanceof NavigationStart),
		),
		{ initialValue: true },
	);
}
