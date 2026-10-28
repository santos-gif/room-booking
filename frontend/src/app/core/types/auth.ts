export const MAJORS = [
	'Information Technology',
	'Management',
	'Culinary Arts',
	'Visual Communication Design',
	'Accounting',
	'Architecture',
	'Business Information System',
	'Civil Engineering',
	'Hospitality & Tourism',
	'Interior Design',
	'Urban Planning',
	'Dosen/Staff',
] as const;

export type Major = (typeof MAJORS)[number];

export interface AuthenticatedUser {
	id: string;
	email: string;
	name: string | null;
	nim: number | null;
	major: Major | null;
	role: 'student' | 'staff';
	onboarding_complete: boolean;
}
