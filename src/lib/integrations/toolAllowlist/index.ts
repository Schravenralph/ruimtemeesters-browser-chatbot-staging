// Per-persona MCP tool-name allowlist filter.
//
// Backstory: a persona in Ruimtemeesters (RO/Juridisch/Commercieel) is
// configured with a list of MCP tool *servers* it can reach. Until this
// module, that was the only access knob — assign a server, the persona
// gets every tool on it. With 117 tools across 9 servers, the model was
// presented with ~80 tools at chat start for the RO persona alone,
// which both burns input tokens every turn and degrades the model's
// ability to pick the right tool from a wall of similar descriptions
// (six `*_at_point` variants, four compliance get/list/spatial tools,
// etc.).
//
// The fix is a per-tool-name allowlist declared in `personas.yaml`,
// seeded into OpenWebUI's model meta under `meta.toolAllowlist`, and
// applied here at chat-completion assembly time. The filter walks each
// tool server's `specs` array, keeps any tool whose name matches an
// allowlist entry, and drops servers that end up with zero tools so we
// don't ship empty servers to the model (which would confuse it).
//
// Pattern syntax: bare names match exactly (`bag_info_at_point` →
// matches only that tool). A trailing `*` is a prefix wildcard
// (`solar_*` matches every name starting with `solar_`). No other
// metacharacters are supported — keeping the surface small avoids
// regex-style escaping bugs in YAML and gives operators a syntax that
// fits on one line of mental model.

/**
 * Minimal shape of a tool spec — matches what `convertOpenApiToToolPayload`
 * in src/lib/utils/index.ts produces. We only read `name`; extra fields
 * (description, parameters) pass through untouched.
 */
export interface ToolSpec {
	name?: string;
	[key: string]: unknown;
}

/**
 * Minimal shape of a tool-server entry — matches the structure produced
 * by `getToolServersData` in src/lib/apis/index.ts. The filter reads
 * `specs` and copies the rest of the fields verbatim.
 */
export interface ToolServer {
	specs?: ToolSpec[];
	[key: string]: unknown;
}

/**
 * Match a single tool name against a single allowlist pattern. Two
 * shapes:
 *   - exact: `bag_info_at_point` matches only `bag_info_at_point`
 *   - prefix: `solar_*` matches every name where `solar_` is a prefix
 *
 * Empty/blank pattern is intentionally never a match — keeps the
 * "absent = no exposure" invariant from the seeder consistent here.
 */
export function matchesPattern(name: string, pattern: string): boolean {
	if (!name || !pattern) return false;
	if (pattern.endsWith('*')) {
		const prefix = pattern.slice(0, -1);
		// A pattern of just `*` would match everything — refuse it.
		// Operators that want "no filtering" should not ship an
		// allowlist at all (and per seeder semantics, that means no
		// tools). Anyone needing a real escape hatch can list patterns
		// explicitly per server prefix.
		if (prefix.length === 0) return false;
		return name.startsWith(prefix);
	}
	return name === pattern;
}

/**
 * Does any pattern in `patterns` match `name`?
 */
export function matchesAnyPattern(name: string, patterns: readonly string[]): boolean {
	for (const pattern of patterns) {
		if (matchesPattern(name, pattern)) return true;
	}
	return false;
}

/**
 * Filter every tool server's `specs` array by the persona's allowlist.
 *
 * Behavior:
 *   - `patterns` is null/undefined/empty → drop every spec from every
 *     server, then drop every server (the model sees no tools). This
 *     mirrors the strict "no allowlist = no tools" default that the
 *     seed_personas.py write path enforces.
 *   - `patterns` is non-empty → keep specs whose name matches any
 *     pattern. Servers that lose all their specs are dropped.
 *
 * Servers whose `specs` array is missing or empty are passed through
 * unchanged — they're either error envelopes (from a server fetch
 * failure) or non-MCP services that don't surface tools to the LLM.
 * Filtering an error envelope would lose the error message; leaving
 * it untouched preserves the operator's ability to see what failed.
 */
export function filterToolsByAllowlist(
	toolServers: readonly ToolServer[],
	patterns: readonly string[] | null | undefined
): ToolServer[] {
	const safePatterns = patterns ?? [];
	const out: ToolServer[] = [];
	for (const server of toolServers) {
		// Pass-through servers without a specs array (errors, non-MCP).
		if (!Array.isArray(server?.specs)) {
			out.push(server);
			continue;
		}
		// Empty allowlist → no tools survive. Don't even ship the
		// server entry; an empty `specs` array could confuse the model.
		if (safePatterns.length === 0) {
			continue;
		}
		const keptSpecs = server.specs.filter(
			(spec) => typeof spec?.name === 'string' && matchesAnyPattern(spec.name, safePatterns)
		);
		if (keptSpecs.length === 0) {
			// All specs were filtered out → drop the server entirely
			// rather than ship an empty server (same reasoning as the
			// empty-patterns branch above).
			continue;
		}
		out.push({ ...server, specs: keptSpecs });
	}
	return out;
}
