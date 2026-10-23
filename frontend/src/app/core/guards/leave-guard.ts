import { inject } from '@angular/core';
import { CanDeactivateFn } from '@angular/router';
import { NavigationLock } from '../services/navigation-lock';

/** Blocks leaving a page (navbar, back button) while a save is in flight. */
export const unlessLocked: CanDeactivateFn<unknown> = () => !inject(NavigationLock).locked();
