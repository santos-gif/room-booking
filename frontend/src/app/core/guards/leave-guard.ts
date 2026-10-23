import { inject } from '@angular/core';
import { CanDeactivateFn } from '@angular/router';
import { NavigationLock } from '../services/navigation-lock';
import { hasCookie } from '../utils/cookies';

/**
 * Blocks leaving a page (navbar, back button) while a save is in flight. Without a session the save
 * can never finish (the server answers 401), so the student must be able to leave for sign-in.
 * Relies on csrf_token being cleared together with the session (see auth-refresh-interceptor).
 */
export const unlessLocked: CanDeactivateFn<unknown> = () =>
	!inject(NavigationLock).locked() || !hasCookie('csrf_token');
