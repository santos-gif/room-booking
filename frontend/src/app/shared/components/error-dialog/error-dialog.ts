import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
@Component({
	imports: [MatButtonModule, MatDialogModule],
	selector: 'app-error-dialog',
	styleUrl: './error-dialog.css',
	templateUrl: './error-dialog.html',
})
export class ErrorDialog {
	protected dialogData = inject<{ errorMessage: string }>(MAT_DIALOG_DATA);
}
