// Auth bridge to the Ruimtemeesters Document-Generator embed (WI-006).
//
// Why this exists:
// - The DG embed runs as a Web Component (<rm-doc-generator>) loaded from
//   https://doc-gen.datameesters.nl/rm-doc-generator.js. Its API client
//   expects `Authorization: Bearer <clerk-jwt>` for all calls back to
//   doc-gen.datameesters.nl/api/*.
// - The chatbot does NOT hold a Clerk JWT in its frontend today. Its
//   `token` cookie is OpenWebUI's own JWT; the Clerk OIDC id-token is in
//   the HttpOnly `oauth_id_token` cookie, only the chatbot backend reads
//   it (token_forwarding.py).
// - ADR-0002 rejected `@clerk/react` (the React provider) and Clerk Pro
//   satellite mode. It did NOT reject `@clerk/clerk-js`, the vanilla
//   framework-agnostic browser client. This module pulls in clerk-js only
//   to mint tokens against the existing browser-side Clerk session that
//   the OIDC flow already established (via `__client_uat` etc. on the
//   .datameesters.nl scope) — we are not establishing a new session.
//
// Lazy singleton: the Clerk client only initialises when something
// actually asks for a token (the /documents route mounts the embed). No
// cost paid on pages that don't touch the DG integration.

import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

// `$env/dynamic/public` rather than `$env/static/public`: at build time
// the var may not yet be set in CI / fresh checkouts, but the chatbot
// still needs to compile. `dynamic` resolves at runtime, returning
// `undefined` when unset, which the `loadClerk` branch below handles
// with a clear error message.
const PUBLIC_CLERK_PUBLISHABLE_KEY = env.PUBLIC_CLERK_PUBLISHABLE_KEY ?? '';

let clerkInstance: import('@clerk/clerk-js').Clerk | null = null;
let loadPromise: Promise<import('@clerk/clerk-js').Clerk | null> | null = null;

/**
 * Load the Clerk JS client once per page, against the user's existing
 * .datameesters.nl Clerk session. Returns `null` if no publishable key is
 * configured — the caller should treat that as a configuration error and
 * surface a clear UI message instead of crashing.
 *
 * The `clerk.load()` call hits Clerk's Frontend API (https://clerk.<env>.com)
 * over the network the first time; subsequent calls return the same
 * loaded instance instantly.
 */
async function loadClerk(): Promise<import('@clerk/clerk-js').Clerk | null> {
	if (!browser) return null;
	if (clerkInstance) return clerkInstance;
	if (loadPromise) return loadPromise;
	if (!PUBLIC_CLERK_PUBLISHABLE_KEY) {
		// Hard-fail at the call site rather than silently using a
		// non-existent client. The /documents route catches and shows a
		// "configure PUBLIC_CLERK_PUBLISHABLE_KEY" message.
		return null;
	}

	loadPromise = (async () => {
		const { Clerk } = await import('@clerk/clerk-js');
		const c = new Clerk(PUBLIC_CLERK_PUBLISHABLE_KEY);
		await c.load();
		clerkInstance = c;
		return c;
	})();
	return loadPromise;
}

/**
 * Return a fresh Clerk JWT for the current user, or `null` if Clerk is
 * not configured / no active session. Used by the DG embed's
 * `auth-token` attribute and refreshed whenever Clerk's session token
 * rotates (Clerk auto-refreshes every ~60 s for JWTs with a default
 * lifetime).
 *
 * Callers that mount the embed should re-read this on a polling
 * interval OR subscribe to Clerk's `addListener` so the embed's token
 * stays fresh — a stale JWT will fail backend calls with a 401 that
 * surfaces via the embed's error events.
 */
export async function getDocGenAuthToken(): Promise<string | null> {
	const clerk = await loadClerk();
	if (!clerk) return null;
	if (!clerk.session) return null;
	try {
		await ensureActiveOrganization(clerk);
		// Re-read clerk.session: setActive() inside ensureActiveOrganization
		// replaces the session reference with one whose JWT includes o.id.
		const session = clerk.session;
		if (!session) return null;
		return await session.getToken();
	} catch {
		// Network blip / expired refresh token. Returning null lets the
		// caller show a "please sign in again" message rather than
		// crashing the embed.
		return null;
	}
}

/**
 * Make sure the Clerk session has an active organisation before we mint
 * the JWT for DG.
 *
 * Why: DG's backend requires `auth.sessionClaims.o.id` and 401s with
 * `WorkspaceRequiredError` ("geen toegang tot deze werkruimte") when
 * absent. Clerk only populates `o.id` after the user has selected an
 * active org via `setActive({ organization })` — there is no Backend-
 * API equivalent to seed it (verified live: PATCH on
 * `/v1/users/{id}.last_active_organization_id` is accepted but silently
 * ignored). Without this bridge, a fresh sign-in carries no org and
 * every user hits the workspace-required path.
 *
 * Strategy: if the session already has an active org (because the user
 * picked one earlier in the session or in a sibling app), keep it.
 * Otherwise scan the user's memberships and pick a default: prefer
 * "Ruimtemeesters" (the primary org for everyone except the Prophys-
 * only contingent), else fall back to the first membership. No-op for
 * users with zero org memberships — DG will still reject them, but the
 * fix for that is server-side (seat them via scripts/seed_clerk_orgs.py).
 *
 * Multi-org users (Ralph, Ron, Jarko, Bruno) land in Ruimtemeesters by
 * default; they can switch later via a future OrganizationSwitcher in
 * the chrome.
 */
async function ensureActiveOrganization(
	clerk: import('@clerk/clerk-js').Clerk,
): Promise<void> {
	// Existing active-org context wins — never override a user's
	// explicit choice if they've already switched.
	const existing = (clerk as unknown as { organization?: { id?: string } | null }).organization;
	if (existing?.id) return;

	const memberships = clerk.user?.organizationMemberships ?? [];
	if (memberships.length === 0) return;

	const preferred =
		memberships.find((m) => m.organization?.name?.toLowerCase() === 'ruimtemeesters') ??
		memberships[0];
	if (!preferred?.organization?.id) return;

	try {
		await clerk.setActive({ organization: preferred.organization.id });
	} catch {
		// setActive can fail if the org has been deleted server-side
		// between membership-list fetch and now. Swallow — caller will
		// just get a no-org JWT and DG will surface workspace_required.
	}
}

/**
 * Subscribe to session changes so the host can re-read the token when
 * Clerk rotates it. Returns an unsubscribe function.
 */
export async function onDocGenAuthChange(listener: () => void): Promise<() => void> {
	const clerk = await loadClerk();
	if (!clerk) return () => {};
	return clerk.addListener(() => listener());
}
