# ADR-0012: Frontend strategy — branded OpenWebUI core + custom service-pattern UIs

**Date:** 2026-05-08
**Status:** Accepted

## Context

The 2026-05-08 architecture session evaluated the Ruimtemeesters AI surface strategy across three axes:

1. **Chat-frontend choice** — keep OpenWebUI, replace it with a custom build, or migrate to a different framework (Letta, Claude Agent SDK + DIY, Claude Managed Agents)
2. **Branding** — accept OpenWebUI's default branding or commit to a Ruimtemeesters identity across the chat surface
3. **Embedded AI in sibling apps** — iframe pattern (current) vs service pattern (custom domain UI calling chatbot's API)

This ADR records the decisions on all three, taken together because they're load-bearing on each other.

## Decisions

### 1. OpenWebUI as the canonical chat frontend (committed)

OpenWebUI remains the production chat frontend for `chatbot.datameesters.nl`. We continue to invest in our fork (auth, BOPA inlets, admin pages, MCP wiring, etc.) rather than migrating to a different stack.

Considered and rejected alternatives:

- **Claude Agent SDK + DIY backend.** Open source, fully Anthropic-native, but requires rebuilding everything OpenWebUI provides (multi-user auth, persistence, streaming, admin UI, i18n, tool registry, filter pipeline, mobile PWA). Estimated months of work to reach parity — would consume the team's bandwidth on infrastructure rather than product.
- **Claude Managed Agents** (Anthropic's beta hosted agent platform). Most attractive on capability — Skills, Memory tool, "Dreaming" consolidation, multi-agent orchestration, sandboxed execution, all built in. Rejected on vendor lock: hosted only on Anthropic's infrastructure, beta status, no self-host story. Vendor lock-in at the platform level is qualitatively worse than at the model level. Re-evaluate if/when a self-host or hybrid option ships.
- **Letta.** Opinionated runtime ("agents run inside Letta"); doesn't compose cleanly with our existing MCP ecosystem. Rejected.
- **LibreChat / AnythingLLM / Big AGI / similar.** Same provider-agnostic limitations as OpenWebUI, with less mature ecosystems and less of our investment carried forward. Rejected.

### 2. Anthropic-native pipeline (deferred — not "no", "not yet")

Today the chatbot routes Claude calls through OpenWebUI's OpenAI-compat path. This strips Anthropic-native features (Skills, Memory tool, computer-use, extended thinking, native prompt-cache controls, batch API).

We **do not commit** to building an Anthropic-native pipeline now. The path when we do is a Pipe (Python function inside OpenWebUI's pipeline that uses the Anthropic SDK directly), not a backend swap.

**Trigger to re-open:** a concrete missing Anthropic feature becomes a real pain point — e.g. token-budget bloat from system-prompt-loaded skills (would be solved by Skills), or a workflow that requires extended-thinking budget tokens, or computer-use becomes load-bearing for an advisor task. At that point we scope a Pipe; this ADR gets a follow-up section recording the trigger and the build plan.

We explicitly accept that until then, our chatbot does not benefit from Anthropic features as they ship. That's the trade we're making for ecosystem preservation.

### 3. Brand OpenWebUI as Ruimtemeesters (committed)

The OpenWebUI fork at `chatbot.datameesters.nl` is the user-facing chat product. It currently carries OpenWebUI default branding (name, logo, colour palette, copy). We commit to a full Ruimtemeesters rebrand of this surface.

Scope of the rebrand:

- **Visual identity** — logo, favicon, splash, PWA icons, app name in the title/manifest
- **Theme** — colour palette aligned with Ruimtemeesters brand (Tailwind theme overrides; not a fork-wide CSS rewrite)
- **Copy** — UI strings that say "Open WebUI" → "Ruimtemeesters" or appropriate; sign-in / sign-up / empty-state copy in the brand voice
- **Email templates** — any transactional templates the fork sends
- **i18n** — every brand-string change goes through `npm run i18n:parse` so all 60 locale JSONs stay consistent (per `feedback_i18n_regen_after_new_keys.md`)
- **Documentation** — internal doc references that name the product

Out of scope of this ADR (kept for separate future work):

- Major UX redesign or re-flow of the chat experience (we're rebranding, not rebuilding)
- Customer-onboarding marketing pages (those live in product-docs / a separate marketing site)
- Geoportaal's custom UI — that's ADR-0011, not part of the OWUI rebrand

The rebrand should be reversible at the `git revert` level — kept on a single feature branch, applied as a bounded set of asset swaps + theme tokens + copy edits. Future OpenWebUI upstream syncs should not be made harder by the rebrand.

### 4. Custom service-pattern UI on Geoportaal (committed — see ADR-0011)

Geoportaal will receive a fully custom AI experience, _not_ an iframe of `chatbot.datameesters.nl/embed`. The custom UI calls OpenWebUI's HTTP API (`/api/chat/completions`, `/api/v1/chats`, `/api/v1/memories`) with the shared Clerk session cookie. Domain-aware affordances (proactive contextual bubbles, in-canvas tool result rendering, deeply embedded interactions) are the goal.

Detailed scope, build order, trade-offs, and the explicit "what this does NOT unlock" caveat are in **ADR-0011: Service-pattern AI surfaces in sibling apps**.

The relationship between this ADR and ADR-0011: ADR-0012 (this one) is the parent frontend strategy; ADR-0011 is the surface-specific implementation pattern. The iframe pattern remains the fallback for surfaces that don't justify a custom build — Databank, Projectbeheer, etc. iframe in the meantime; promote to service-pattern individually if/when the case is earned.

## Rationale

The four decisions cohere around one principle: **preserve the OpenWebUI investment as the canonical durable chat surface, while permitting bespoke service-pattern surfaces where domain UX is the point.**

- OpenWebUI's value is durable: auth, persistence, streaming, multi-model, admin, i18n, mobile, accessibility — all tested in the wild and not where we want to spend engineering time
- The OWUI stripped-down OpenAI-compat path is the cost we pay for that. It's a real cost (no Skills, no Memory tool) but it's deferrable until a missing feature actually bites
- Branding is a low-risk, high-perception change that closes the "this is somebody else's chat product" gap without touching architecture
- Service-pattern UIs are the ambitious bet — domain-aware AI integration is genuinely category-shifting UX, and Geoportaal's spatial UI is the right test bed
- Iframe stays as the cheap default for surfaces where the custom investment doesn't pay off

## Consequences

**Positive:**

- We continue shipping product features against a stable frontend
- Branded chat starts to feel like our product
- Geoportaal becomes a category-leading AI surface for spatial planning, distinct from "another chat box"
- Two patterns (iframe + service) lets us right-size each sibling-app integration

**Negative:**

- Anthropic-native features remain absent from `chatbot.datameesters.nl` until we revisit the Pipe decision
- Branding work has to be redone (or re-merged) on each upstream OpenWebUI sync
- Geoportaal's custom UI is real engineering work; the first proof point will reveal unexpected costs (CORS quirks, SSE rendering edge cases, tool-result rendering scope)
- We're consciously not on the bleeding edge of agent platforms (Managed Agents) — we trade capability for control

## Triggers to revisit

- A specific Anthropic-native feature becomes a measurable pain point → revisit §2 (Pipe scope)
- Claude Managed Agents leaves beta with self-host or hybrid options → revisit §1 (whether to migrate parts of the stack)
- Custom Geoportaal UI proof-of-concept reveals the cost is materially higher than expected → revisit ADR-0011 (revert to iframe or scope down)
- OpenWebUI upstream rebrand-friendliness regresses (e.g. they hard-code branding deeper) → revisit §3 (consider a heavier fork divergence or a vendor approach)
- Token spend on system-prompt-loaded skills exceeds API cost of Pipe + Skills → §2 trigger

## Related ADRs

- **ADR-0001** — Fork OpenWebUI (parent decision; this ADR continues the commitment)
- **ADR-0007** — Multi-surface platform (OpenWebUI as backend-of-record; this ADR refines the _surface_ layer of that)
- **ADR-0008** — Embedded chat via API (the API contract sibling apps consume)
- **ADR-0009** — Shared session cookie domain (the auth mechanism that makes service pattern possible)
- **ADR-0011** — Service-pattern AI surfaces in sibling apps (the implementation pattern for §4)

## Open work tracked separately

These follow from this ADR but are not its scope:

- Branding spec (assets, palette, copy) — needs a product/design pass before implementation
- Geoportaal CORS + auth proof-of-concept — half-day spike, validates ADR-0011's premise
- Geoportaal NOx-popup proof point build — first concrete service-pattern interaction (~1 week per ADR-0011's estimate)
