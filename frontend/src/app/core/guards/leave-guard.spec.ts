import { TestBed } from '@angular/core/testing';
import { NavigationLock } from '../services/navigation-lock';
import { unlessLocked } from './leave-guard';

describe('unlessLocked', () => {
	const canLeave = (): unknown =>
		TestBed.runInInjectionContext(() =>
			unlessLocked(null, null as never, null as never, null as never),
		);

	afterEach(() => {
		document.cookie = 'csrf_token=; max-age=0';
	});

	it('lets the student leave when nothing is saving', () => {
		document.cookie = 'csrf_token=abc';
		expect(canLeave()).toBe(true);
	});

	it('holds the student on the page while a save runs and the session is alive', () => {
		document.cookie = 'csrf_token=abc';
		TestBed.inject(NavigationLock).locked.set(true);
		expect(canLeave()).toBe(false);
	});

	it('lets the student leave a running save once the session cookie is gone', () => {
		TestBed.inject(NavigationLock).locked.set(true);
		expect(canLeave()).toBe(true);
	});
});
