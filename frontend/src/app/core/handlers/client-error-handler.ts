import { ErrorHandler, inject, Injectable, Injector, NgZone } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { ErrorDialog } from '../../shared/components/error-dialog/error-dialog';

const CHUNK_FAILURE =
	/Loading chunk|Failed to fetch dynamically imported module|error loading dynamically imported module/i;
// Browsers report this harmless layout notice as an error event; it is not worth a dialog.
const HARMLESS = /ResizeObserver loop/i;
const RELOAD_KEY = 'chunk-reload-at';

/**
 * Last line of defence for errors nothing else caught. It never traps the student: the notice can be
 * closed, only one shows at a time, and the page reloads only when a lazy page failed to download
 * (a stale deploy), and then at most once every 30 seconds so a dead backend cannot cause a reload loop.
 */
@Injectable()
export class ClientErrorHandler implements ErrorHandler {
	private readonly injector = inject(Injector);
	private readonly zone = inject(NgZone);

	handleError(error: unknown): void {
		console.error('Unhandled frontend error:', error);
		const message = error instanceof Error ? error.message : String(error);
		if (HARMLESS.test(message)) {
			return;
		}
		if (CHUNK_FAILURE.test(message)) {
			this.reloadOnce();
			return;
		}
		this.zone.run(() => {
			const dialog = this.injector.get(MatDialog);
			if (dialog.openDialogs.length === 0) {
				dialog.open(ErrorDialog, {
					data: {
						errorMessage:
							'Something went wrong. Close this and carry on; if a page looks stuck, reload it.',
					},
					width: '400px',
				});
			}
		});
	}

	private reloadOnce(): void {
		try {
			const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0);
			if (Date.now() - last < 30_000) {
				return;
			}
			sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
		} catch {
			// Storage blocked: reloading once is still better than a dead page.
		}
		window.location.reload();
	}
}
