# Forge Spec: postMessage Bearer handshake (M1)

**Cycle:** 2 | **Clock:** 0.2h elapsed | **Size:** medium

## What

The chatbot frontend accepts a Clerk session JWT pushed in via `postMessage` from an allowlisted `*.datameesters.nl` parent origin, holds it in module-level memory (not localStorage), and forwards it as `Authorization: Bearer <jwt>` on every fetch + the Socket.IO handshake. Emits `{ type: 'rm:chatbot-ready' }` on mount so the parent knows when to push the first token without racing.

## Why

Unblocks M2 (shared ChatPanel component) for the iframe-bridge programme. The native Geoportaal chat panel already proves the backend half — `clerk_sso.py` + `_try_clerk_jwt_auth` in `utils/auth.py` is battle-tested. With this frontend half, an advisor inside Geoportaal / Databank gets one continuous Clerk session without bouncing through OIDC inside the iframe. Safari ITP + Chrome 3PC deprecation make any cookie-based reliance brittle; Bearer-in-memory is the only sound path.

## Success criteria

1. From a hand-rolled parent on `*.datameesters.nl`, pushing `{ type: 'rm:clerk-token', token: '<jwt>' }` results in a subsequent `GET /api/v1/auths/` returning 200 with the correct Clerk user — with no `token` cookie set.
2. Socket.IO handshake carries the Bearer token in its `auth` payload, so streaming a chat completion works inside the iframe.
3. Messages from non-allowlisted origins are silently dropped (no logging side-channel that leaks origin info).
4. Unit tests cover origin allowlist + envelope validation for both the inbound `rm:clerk-token` shape and the outbound `rm:chatbot-ready` shape.

## Approach

- New `src/lib/bridge/clerkToken.ts` — protocol surface (mirrors the `geoportaal.ts` pattern: allowlist, envelope validators, send helper). Keeps the cross-protocol bridge code consistent.
- New `src/lib/stores/clerkBridge.ts` — module-level `_bearerToken` + a Svelte store for components that want to react. Module-level keeps it ephemeral; reload starts fresh.
- `+layout.svelte` patch — register a `message` listener that validates origin + parses payload, calls `setBearerToken(token)`, then forces a Socket.IO reconnect so the new auth payload is sent. Send `rm:chatbot-ready` to the parent on mount when in iframe context.
- `+layout.svelte` patch — install a `window.fetch` proxy that, when a bridge token is set, injects/overrides `Authorization: Bearer <token>` on every outbound request to a same-origin URL. Existing `localStorage.token` references continue to work (the proxy overrides them when present).
- Tests — unit tests for the protocol parsers + a vitest test for the fetch proxy injection.

## Not doing

- Step 6 from the issue (skip OIDC redirect when token present). The redirect only fires when there's no session; once the Bearer token authenticates the request, the redirect path doesn't trigger anyway. Optional optimization — defer to a later cycle if it surfaces.
- Multiple parallel tokens (one per origin). The bridge supports one token at a time; the parent is the source of truth.
- Re-auth on token expiry. The parent pushes a fresh `rm:clerk-token` on Clerk refresh; the proxy + socket pick it up on next request / reconnect.
- M2 (shared ChatPanel component). That's the consumer of this protocol on the parent side; out of scope for this PR.
