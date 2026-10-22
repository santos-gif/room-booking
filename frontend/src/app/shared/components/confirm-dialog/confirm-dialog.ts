import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';

export interface ConfirmDialogData {
	title: string;
	message: string;
	confirmLabel: string;
	cancelLabel: string;
}

/** Yes/no question. Closes with true when the student confirms, false otherwise. */
@Component({
	imports: [MatButtonModule, MatDialogModule],
	selector: 'app-confirm-dialog',
	templateUrl: './confirm-dialog.html',
})
export class ConfirmDialog {
	protected readonly data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
}
