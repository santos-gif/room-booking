import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SigninGoogleBtn } from './signin-google-btn';

describe('SigninGoogleBtn', () => {
	let component: SigninGoogleBtn;
	let fixture: ComponentFixture<SigninGoogleBtn>;

	beforeEach(async () => {
		await TestBed.configureTestingModule({
			imports: [SigninGoogleBtn],
			// LoginService reads the route's query params and AuthService needs HttpClient.
			providers: [provideRouter([]), provideHttpClient()],
		}).compileComponents();

		fixture = TestBed.createComponent(SigninGoogleBtn);
		component = fixture.componentInstance;
		await fixture.whenStable();
	});

	it('should create', () => {
		expect(component).toBeTruthy();
	});
});
