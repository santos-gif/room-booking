export interface BookingAppointment {
	id: string;
	booker_id: string;
	room_number: 1 | 2;
	start_time: string;
	end_time: string;
	status: 'pending' | 'confirmed' | 'cancelled';
	sync_status: 'pending' | 'synced' | 'failed' | 'legacy';
}

export interface AvailableSlot {
	start_time: string;
	end_time: string;
	available: boolean;
}

export interface Availability {
	bookings_used: number;
	bookings_remaining: number;
	slots: AvailableSlot[];
	/** Why the room is closed on this day (staff closed it); null when it is open. */
	closed_reason?: string | null;
}

export interface BookingPayload {
	room_number: 1 | 2;
	start_time: string;
}
