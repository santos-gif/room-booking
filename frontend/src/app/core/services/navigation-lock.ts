import { Injectable, signal } from '@angular/core';

/** True while something that must not be interrupted is running (saving a booking). */
@Injectable({ providedIn: 'root' })
export class NavigationLock {
	readonly locked = signal(false);
}
