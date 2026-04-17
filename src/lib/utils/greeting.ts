export interface UserWithName {
	name?: string | null;
}

export function getFirstName(user: UserWithName | null | undefined): string | null {
	if (!user || typeof user.name !== 'string') return null;
	const trimmed = user.name.trim();
	if (trimmed.length === 0) return null;
	const first = trimmed.split(/\s+/)[0];
	return first.length > 0 ? first : null;
}
