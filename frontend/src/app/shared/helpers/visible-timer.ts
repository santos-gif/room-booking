import { EMPTY, fromEvent, map, Observable, startWith, switchMap, timer } from 'rxjs';

/**
 * Emits now and then every `periodMs`, but only while the tab is visible. A hidden tab makes no
 * requests (saves Vercel invocations); coming back to the tab refreshes straight away.
 */
export function visibleTimer(periodMs: number): Observable<number> {
	return fromEvent(document, 'visibilitychange').pipe(
		startWith(null),
		map(() => !document.hidden),
		switchMap((visible) => (visible ? timer(0, periodMs) : EMPTY)),
	);
}
