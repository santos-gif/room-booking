import { Component } from '@angular/core';
import { AppHeader } from '../../../shared/components/app-header/app-header';
import { ClosuresPanel } from '../components/closures-panel/closures-panel';
import { OverridePanel } from '../components/override-panel/override-panel';
import { StaffService } from '../service/staff.service';

/** For staff only (the route guard hides it, the server refuses everyone else). */
@Component({
	providers: [StaffService],
	imports: [AppHeader, ClosuresPanel, OverridePanel],
	selector: 'app-staff-page',
	templateUrl: './staff-page.html',
	styleUrl: './staff-page.css',
})
export class StaffPage {}
