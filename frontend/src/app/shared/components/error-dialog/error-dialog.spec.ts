import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { ErrorDialog } from './error-dialog';

describe('ErrorDialog', () => {
	let component: ErrorDialog;
	let fixture: ComponentFixture<ErrorDialog>;

	beforeEach(async () => {
		await TestBed.configureTestingModule({
			imports: [ErrorDialog],
			providers: [
				{
					provide: MAT_DIALOG_DATA,
					useValue: { errorMessage: 'Something went wrong.' },
				},
			],
		}).compileComponents();

		fixture = TestBed.createComponent(ErrorDialog);
		component = fixture.componentInstance;
		await fixture.whenStable();
	});

	it('should create', () => {
		expect(component).toBeTruthy();
		expect(fixture.nativeElement.textContent).toContain('Something went wrong.');
	});
});
