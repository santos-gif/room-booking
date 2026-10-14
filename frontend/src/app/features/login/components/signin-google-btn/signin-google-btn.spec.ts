import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SigninGoogleBtn } from './signin-google-btn';

describe('SigninGoogleBtn', () => {
	let component: SigninGoogleBtn;
	let fixture: ComponentFixture<SigninGoogleBtn>;

	beforeEach(async () => {
		await TestBed.configureTestingModule({
			imports: [SigninGoogleBtn],
		}).compileComponents();

		fixture = TestBed.createComponent(SigninGoogleBtn);
		component = fixture.componentInstance;
		await fixture.whenStable();
	});

	it('should create', () => {
		expect(component).toBeTruthy();
	});
});
