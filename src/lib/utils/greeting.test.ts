import { describe, expect, it } from 'vitest';

import { getFirstName } from './greeting';

describe('getFirstName', () => {
	it('returns null for undefined user', () => {
		expect(getFirstName(undefined)).toBeNull();
	});

	it('returns null for null user', () => {
		expect(getFirstName(null)).toBeNull();
	});

	it('returns null when name is missing', () => {
		expect(getFirstName({})).toBeNull();
	});

	it('returns null when name is an empty string', () => {
		expect(getFirstName({ name: '' })).toBeNull();
	});

	it('returns null when name is whitespace only', () => {
		expect(getFirstName({ name: '   ' })).toBeNull();
	});

	it('returns the first token of a multi-part name', () => {
		expect(getFirstName({ name: 'Ralph Schraven' })).toBe('Ralph');
	});

	it('returns the full name when single token', () => {
		expect(getFirstName({ name: 'Frank' })).toBe('Frank');
	});

	it('trims leading whitespace before splitting', () => {
		expect(getFirstName({ name: '  Ralph de Jong' })).toBe('Ralph');
	});

	it('handles common Dutch tussenvoegsels without leaking them', () => {
		expect(getFirstName({ name: 'Ralph de Jong' })).toBe('Ralph');
		expect(getFirstName({ name: 'Sander van den Berg' })).toBe('Sander');
	});
});
