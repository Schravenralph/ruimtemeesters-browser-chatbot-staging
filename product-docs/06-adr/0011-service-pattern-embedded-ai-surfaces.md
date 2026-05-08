# ADR-0011: Service-pattern AI surfaces in sibling apps (exploration)

**Date:** 2026-05-08
**Status:** Accepted (2026-05-08) — committed as the working pattern for the Geoportaal embedded AI experience. Iframe pattern remains the fallback for surfaces that don't justify custom-UI investment. See ADR-0012 for the parent frontend strategy.

## Context

ADR-0007 established that OpenWebUI is the backend-of-record and that sibling apps (Geoportaal, Databank, Projectbeheer) consume conversations and tools via the REST API. It listed "embedded chat panels" as one surface type but did not specify *how* those panels are built.

In practice today, "embedded chat panel" means **iframe** — a sibling app loads `chatbot.datameesters.nl/embed` in a frame and the user sees the chatbot's own UI inside the sibling page. PR #54 shipped this for Geoportaal. It works, it's cheap, and conversation history + memory are automatically shared because both surfaces hit the same OpenWebUI instance under the same Clerk identity.

A more ambitious alternative emerged in conversation on 2026-05-08: build sibling-app UIs that **call OpenWebUI's API directly** with their own custom rendering, rather than embedding OpenWebUI's UI. The chat becomes a *service* the surface uses, not a *destination* you visit. The exemplar that made this concrete:

> *In Geoportaal, the user pans to an area where NOx is in the 95th percentile this week. A small face + speech bubble pops up: "Looks like NoX is unusually high this week — want me to run a scan in the area?" Click yes, the bubble expands into a result panel. The scan output renders directly as a heatmap layer on the actual map, not as text in a chat box.*

This pattern is closer to how Notion AI, Linear AI, GitHub Copilot Chat, and Cursor's inline chat are built — domain-aware UI talking to an AI service backend, not a chrome-heavy chat box.

## Considered approaches

### A. Iframe pattern (current)

- Sibling app loads `chatbot.datameesters.nl/embed` in an iframe
- OpenWebUI renders its own UI inside the frame
- Conversation history, memory, models, tools, filters — all shared automatically because it's literally the same backend + UI
- **Pros:** zero new infrastructure; ships what works today; no per-surface UI maintenance; conversation continuity is automatic
- **Cons:** the chatbot UI is the same in every surface; no domain-specific affordances (proactive bubbles, in-canvas tool result rendering, etc.); chrome eats screen space

### B. Service pattern (this ADR's exploration)

- Sibling app builds its own UI components (bubbles, panels, in-canvas renderings)
- Sibling app's frontend calls `chatbot.datameesters.nl/api/chat/completions` (OpenAI-compatible, streaming) and other API endpoints (`/api/v1/chats`, `/api/v1/memories`) with the user's shared `__session` cookie
- Backend behaviour is unchanged: filter inlets fire, MCPs dispatch, memory is recalled, history is persisted with `chat_id`
- **Pros:** domain-aware UX (proactive bubbles, in-canvas rendering of tool results, contextual triggers); conversations still appear in the canonical chat UI for continuity; AI feels deeply embedded rather than bolted-on
- **Cons:** real frontend work per surface (custom UI, SSE streaming consumer, tool result rendering); CORS + auth wiring; no free reuse of OpenWebUI's UI affordances (regen, edit, voice, etc.) unless reimplemented

### C. Sibling app builds its own chat backend

- Sibling app stands up its own conversation store, model dispatch, memory layer
- **Pros:** maximum control
- **Cons:** duplicates OpenWebUI's investment; breaks ADR-0007's "single backend-of-record" principle; cross-surface continuity becomes a real problem (this is when external memory hubs like Hindsight start to matter)
- Rejected on principle: would re-open architectural questions ADR-0007 already settled

## Why we're recording this without deciding

Approach B has high upside but real cost. Concretely:

- The NOx-popup example is a single proof point that needs ~1 week to build end-to-end (CORS, auth, SSE consumer, the bubble UI, one domain-rendered tool result like a heatmap layer)
- Generalising to a pattern (multiple proactive interactions across multiple sibling apps) is template-fill once the first one works, but the first one is real work
- The investment only pays off if we have *real* domain-aware interactions to surface — i.e. signals worth proactively raising, tool results that are better rendered in-canvas than as text. We believe these exist but haven't enumerated them
- The iframe pattern keeps working in the meantime; this is additive, not a migration

We see big potential in this idea — proactive, deeply embedded AI is a categorical UX shift, not a feature tweak — but locking it in now would prematurely commit to scope and effort that needs more shaping.

## Open questions to answer before locking in

1. **Concrete proactive interactions worth building.** Beyond the NOx example, what specific signals in Geoportaal / Databank / Projectbeheer would justify a service-pattern UI? List 5–10 concrete interactions; if the list is thin, the pattern isn't yet earned.
2. **Tool-result rendering reuse.** Each domain-aware rendering (heatmap layer, BAG-info popup, BOPA phase progress bar) is per-surface code. Is there a shared component vocabulary — a typed contract for tool results — that lets us amortise the rendering work? Or does each tool/surface pair need bespoke code?
3. **CORS + auth proof-of-concept.** Does Geoportaal calling `chatbot.datameesters.nl/api/chat/completions` with the Clerk shared cookie actually work end-to-end? Half a day to confirm; should happen before the larger commitment.
4. **Conversation continuity UX.** A conversation started via a Geoportaal popup and then continued in the canonical chatbot UI — is that flow desirable, confusing, or both? Affects whether we share `chat_id` aggressively or namespace it per surface.
5. **MCP registration per surface.** Should sibling apps register their *own* MCPs (e.g. `geoportaal.show_layer`, `geoportaal.fly_to_address`) that the model can call from any surface? Would let the chatbot UI also drive the geoportaal map. Architecturally clean but adds wiring.

## Decision

**Accepted (2026-05-08).** Geoportaal will be the first surface to receive a fully custom service-pattern AI UI, calling `chatbot.datameesters.nl/api/chat/completions` and related endpoints via the shared Clerk session cookie. The iframe-based `/embed` pattern stays available as a fallback / for surfaces where the custom investment isn't justified.

The first concrete proof point remains the NOx-popup scenario (proactive contextual bubble, expanding panel, in-canvas tool result rendering). Build order: CORS + auth POC → SSE consumer → one full proactive interaction end to end → generalize.

This is framed as "try" rather than "ship" — the commitment is to the *attempt*, with the understanding that the proof point may surface unexpected costs that revise scope. If the attempt reveals the cost is materially higher than the value, this ADR gets revised back to "Rejected" with a written postmortem.

**This decision does not commit to:**
- Anthropic-native features (Skills, Memory tool, computer-use, extended thinking) — see ADR-0012 §"Anthropic-native pipeline"
- Replacing OpenWebUI's chat surface for general use — see ADR-0012 §"OpenWebUI as the canonical chat frontend"
- An external memory layer (Hindsight or otherwise) — service pattern uses the same OpenWebUI backend; cross-surface memory continuity is automatic

## Related ADRs

- **ADR-0007** — Multi-surface platform — establishes OpenWebUI as backend-of-record. This ADR lives inside one branch of 0007's design space.
- **ADR-0008** — Embedded chat via API — covers the API contract sibling apps consume. The service pattern is one consumer pattern of that API.
- **ADR-0009** — Shared session cookie domain — the auth mechanism that makes cross-origin API calls from sibling apps possible.

## What this pattern does NOT unlock

To prevent the same confusion that came up while drafting this: the service pattern is a **UI-axis** change. The backend is still OpenWebUI's `/api/chat/completions`, which goes through the OpenAI-compatible facade and strips Anthropic-native features (Skills, Memory tool, computer-use, extended thinking, native prompt-cache controls).

Service pattern alone gets you domain-aware UI. It does not get you Anthropic-native features. Those require a **separate backend change** — a Pipe (Python function inside OpenWebUI that uses the Anthropic SDK directly), which is orthogonal to this ADR.

The two changes compose. If/when both are built, a service-pattern UI is well-positioned to render the additional signals a Pipe surfaces (thinking traces, Skills indicators, Memory tool reads). But neither change implies the other; they're independent commitments.

## Notes for the next session that picks this up

- The NOx proactive popup is the canonical example we used to anchor the discussion; reuse it for any prototype scoping
- The 1-week ballpark for a first proof point is intentionally generous — real number depends on whether CORS surprises us
- Hindsight ADR direction (deferred separately) does *not* depend on this. Service pattern doesn't require an external memory layer for the cases discussed; OpenWebUI native memory + filter inlets is sufficient
- Anthropic-native features (Skills, Memory tool, etc.) are also a separate decision — see "What this pattern does NOT unlock" above
