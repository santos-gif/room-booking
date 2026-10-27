import { Component } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule } from '@angular/material/dialog';

/**
 * Shown over whatever the student was doing when the app session ended. The button is the only way
 * out; the caller decides where it leads.
 */
@Component({
	imports: [MatButtonModule, MatDialogModule],
	selector: 'app-session-expired-dialog',
	templateUrl: './session-expired-dialog.html',
})
export class SessionExpiredDialog {}
