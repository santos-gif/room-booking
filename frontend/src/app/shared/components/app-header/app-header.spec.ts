import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../../core/services/auth-service';
import { AppHeader } from './app-header';

describe('AppHeader (signing out always asks first)', () => {
	function render(answer: boolean) {
		const logout = vi.fn(() => of(null));
		const open = vi.fn(() => ({ afterClosed: () => of(answer) }));
		TestBed.configureTestingModule({
			providers: [
				provideRouter([]),
				{ provide: AuthService, useValue: { logout } },
				{ provide: MatDialog, useValue: { open } },
			],
		});
		const fixture = TestBed.createComponent(AppHeader);
		fixture.detectChanges();
		const button = (
			fixture.nativeElement as HTMLElement
		).querySelector<HTMLButtonElement>('.signout')!;
		return { button, logout, open };
	}

	it('does not sign out on the first tap: it opens the question', () => {
		const { button, logout, open } = render(false);
		button.click();
		expect(open).toHaveBeenCalledTimes(1);
		expect(logout).not.toHaveBeenCalled();
	});

	it('signs out only after the student confirms', () => {
		const { button, logout } = render(true);
		button.click();
		expect(logout).toHaveBeenCalledTimes(1);
	});
});
