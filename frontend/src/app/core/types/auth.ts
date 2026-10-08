
export const MAJORS = [
	'IT',
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
] as const;

export type Major = (typeof MAJORS)[number];

export interface AuthenticatedUser {
	id: string;
	email: string;
	name: string | null;
	nim: number | null;
	major: Major | null;
	onboarding_complete: boolean;
}
