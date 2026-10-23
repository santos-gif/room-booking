/** What an HTTP error looks like to the pages: the status, and the backend's `detail` when it sent one. */
export interface ApiFailure {
	/** "TimeoutError" when rxjs `timeout()` gave up: the server never answered in time. */
	name?: string;
	status?: number;
	error?: { detail?: unknown };
}

/** The backend's own message, only when it is text (never an object or array, which could be anything). */
export function serverDetail(failure: ApiFailure): string | null {
	const detail = failure.error?.detail;
	return typeof detail === 'string' ? detail : null;
}
