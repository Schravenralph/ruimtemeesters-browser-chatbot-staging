// Tests for the per-persona tool-name allowlist filter. Pure logic;
// no DOM, no async. Covers the patterns the seed_personas.py output
// actually produces (exact names + bare-prefix wildcards) plus the
// edge cases that would silently break a persona in production
// (missing patterns, empty patterns, error envelopes from failed
// server fetches, `*` as a pattern).

import { describe, expect, it } from 'vitest';

import {
	filterToolsByAllowlist,
	matchesAnyPattern,
	matchesPattern,
	type ToolServer
} from './index';

describe('matchesPattern', () => {
	it('exact match', () => {
		expect(matchesPattern('bag_info_at_point', 'bag_info_at_point')).toBe(true);
		expect(matchesPattern('bag_info_at_point', 'bag_info_at_point_extra')).toBe(false);
		expect(matchesPattern('bag_info_at_point_extra', 'bag_info_at_point')).toBe(false);
	});

	it('prefix wildcard matches any name with the prefix', () => {
		expect(matchesPattern('solar_summary', 'solar_*')).toBe(true);
		expect(matchesPattern('solar_buildings', 'solar_*')).toBe(true);
		expect(matchesPattern('solar_', 'solar_*')).toBe(true); // edge: prefix-only name
		expect(matchesPattern('solar', 'solar_*')).toBe(false); // missing underscore
		expect(matchesPattern('not_solar_summary', 'solar_*')).toBe(false);
	});

	it('lone `*` is refused (would be a global match)', () => {
		expect(matchesPattern('anything', '*')).toBe(false);
	});

	it('empty inputs never match', () => {
		expect(matchesPattern('', 'bag_info_at_point')).toBe(false);
		expect(matchesPattern('bag_info_at_point', '')).toBe(false);
		expect(matchesPattern('', '')).toBe(false);
	});
});

describe('matchesAnyPattern', () => {
	it('matches when any pattern hits', () => {
		expect(matchesAnyPattern('solar_summary', ['bag_info_at_point', 'solar_*'])).toBe(true);
	});

	it('false when no pattern matches', () => {
		expect(matchesAnyPattern('scoring_compute', ['bag_info_at_point', 'solar_*'])).toBe(false);
	});

	it('empty patterns never match', () => {
		expect(matchesAnyPattern('solar_summary', [])).toBe(false);
	});
});

function makeServer(url: string, names: string[]): ToolServer {
	return {
		url,
		specs: names.map((name) => ({ name, description: `desc for ${name}` }))
	};
}

describe('filterToolsByAllowlist', () => {
	it('keeps specs whose names match an exact pattern', () => {
		const servers = [makeServer('http://rm-geoportaal', ['bag_info_at_point', 'scoring_compute'])];
		const out = filterToolsByAllowlist(servers, ['bag_info_at_point']);
		expect(out).toHaveLength(1);
		expect(out[0].specs).toEqual([
			{ name: 'bag_info_at_point', description: 'desc for bag_info_at_point' }
		]);
	});

	it('keeps specs whose names match a prefix wildcard', () => {
		const servers = [
			makeServer('http://rm-geoportaal', [
				'solar_summary',
				'solar_buildings',
				'solar_panel_profiles',
				'scoring_compute'
			])
		];
		const out = filterToolsByAllowlist(servers, ['solar_*']);
		expect(out).toHaveLength(1);
		expect(out[0].specs?.map((s) => s.name)).toEqual([
			'solar_summary',
			'solar_buildings',
			'solar_panel_profiles'
		]);
	});

	it('drops servers whose every spec was filtered out', () => {
		const servers = [
			makeServer('http://rm-geoportaal', ['bag_info_at_point']),
			makeServer('http://rm-tsa', ['run_population_forecast'])
		];
		const out = filterToolsByAllowlist(servers, ['solar_*']);
		expect(out).toEqual([]);
	});

	it('preserves the server entry when at least one spec survives', () => {
		const servers = [
			makeServer('http://rm-geoportaal', ['bag_info_at_point', 'scoring_compute']),
			makeServer('http://rm-tsa', ['run_population_forecast'])
		];
		const out = filterToolsByAllowlist(servers, ['bag_info_at_point']);
		expect(out).toHaveLength(1);
		expect(out[0].url).toBe('http://rm-geoportaal');
		expect(out[0].specs).toHaveLength(1);
	});

	it('null or undefined patterns ship no tools (strict default)', () => {
		const servers = [makeServer('http://rm-geoportaal', ['bag_info_at_point'])];
		expect(filterToolsByAllowlist(servers, null)).toEqual([]);
		expect(filterToolsByAllowlist(servers, undefined)).toEqual([]);
		expect(filterToolsByAllowlist(servers, [])).toEqual([]);
	});

	it('passes through error envelopes (no specs array) so operators see the failure', () => {
		const errored: ToolServer = { url: 'http://broken', error: 'Connection timed out' };
		const ok = makeServer('http://rm-geoportaal', ['bag_info_at_point']);
		const out = filterToolsByAllowlist([errored, ok], ['bag_info_at_point']);
		expect(out).toHaveLength(2);
		expect(out[0]).toBe(errored);
		expect(out[1].specs).toHaveLength(1);
	});

	it('ignores specs whose name is missing or non-string', () => {
		const server: ToolServer = {
			url: 'http://rm-geoportaal',
			specs: [
				{ name: 'bag_info_at_point' },
				{ name: undefined as unknown as string },
				{ description: 'no name field' } as unknown as { name?: string },
				{ name: 42 as unknown as string }
			]
		};
		const out = filterToolsByAllowlist([server], ['*_at_point', 'bag_info_at_point']);
		expect(out).toHaveLength(1);
		expect(out[0].specs).toEqual([{ name: 'bag_info_at_point' }]);
	});

	it('mixed allowlist with prefix + exact handles geoportaal-sized payload', () => {
		const geoportaal = makeServer('http://rm-geoportaal', [
			'bag_info_at_point',
			'bouwvlak_envelopes_at_point',
			'scoring_compute',
			'scoring_layers',
			'solar_summary',
			'solar_buildings',
			'bopa_scan_at_address',
			'get_compliance_matrix',
			'get_compliance_scans'
		]);
		const out = filterToolsByAllowlist(
			[geoportaal],
			['bag_info_at_point', 'solar_*', 'bopa_*', 'get_compliance_*']
		);
		expect(out).toHaveLength(1);
		const kept = (out[0].specs ?? []).map((s) => s.name).sort();
		expect(kept).toEqual([
			'bag_info_at_point',
			'bopa_scan_at_address',
			'get_compliance_matrix',
			'get_compliance_scans',
			'solar_buildings',
			'solar_summary'
		]);
	});
});
