export interface Appointment {
	id: string;
	booker_id: string;
	room_number: 1 | 2;
	start_time: string;
	end_time: string;
	status: 'pending' | 'confirmed' | 'cancelled';
	sync_status: 'pending' | 'synced' | 'failed' | 'legacy';
}
