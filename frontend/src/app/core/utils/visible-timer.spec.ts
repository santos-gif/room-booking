import { visibleTimer } from './visible-timer';

function setHidden(hidden: boolean): void {
	Object.defineProperty(document, 'hidden', { configurable: true, value: hidden });
	document.dispatchEvent(new Event('visibilitychange'));
}

describe('visibleTimer (no polling for a tab nobody is looking at)', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		setHidden(false);
	});

	afterEach(() => {
		vi.useRealTimers();
		setHidden(false);
	});

	it('ticks immediately, then every period while the tab is visible', () => {
		const ticks: number[] = [];
		const subscription = visibleTimer(1000).subscribe((n) => ticks.push(n));
		vi.advanceTimersByTime(0); // timer(0, …) fires on the next tick, not synchronously
		expect(ticks).toEqual([0]);
		vi.advanceTimersByTime(2000);
		expect(ticks).toEqual([0, 1, 2]);
		subscription.unsubscribe();
	});

	it('stops while the tab is hidden and refreshes at once when it returns', () => {
		const ticks: number[] = [];
		const subscription = visibleTimer(1000).subscribe((n) => ticks.push(n));
		vi.advanceTimersByTime(0);
		setHidden(true);
		vi.advanceTimersByTime(5000);
		expect(ticks).toEqual([0]);
		setHidden(false);
		vi.advanceTimersByTime(0);
		expect(ticks).toEqual([0, 0]);
		subscription.unsubscribe();
	});
});
