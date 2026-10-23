import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';

/**
 * Shown over whatever the student was doing when the app session ended, or when Google stopped accepting
 * the Calendar connection (`reconnect`). The button is the only way out; the caller decides where it leads.
 */
@Component({
	imports: [MatButtonModule, MatDialogModule],
	selector: 'app-session-expired-dialog',
	templateUrl: './session-expired-dialog.html',
})
export class SessionExpiredDialog {
	protected readonly reconnect = inject<{ reconnect: boolean }>(MAT_DIALOG_DATA).reconnect;
}
