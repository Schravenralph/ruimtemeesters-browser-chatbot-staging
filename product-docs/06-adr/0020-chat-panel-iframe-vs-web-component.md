# ADR-0020: In-chat Document panel uses iframe; standalone `/documents/[id]` uses Web Component

**Date:** 2026-05-26
**Status:** Accepted
**Relates to:** ADR-0019 (Clerk-JS for token-minting), Document-Generator ADR-002 (rejected iframes for the standalone embed surface)
**Driver:** WI-014 ship + post-merge question on whether to converge

## Context

The chatbot embeds the Ruimtemeesters Document-Generator in two distinct surfaces:

1. **Standalone `/documents/[id]` route** (WI-006) — full-page editor. Uses the `<rm-doc-generator>` Web Component (loaded from `https://doc-gen.datameesters.nl/rm-doc-generator.js`), mounted by `src/lib/components/documents/DocGenEmbed.svelte`. Auth via `docGenAuth.getDocGenAuthToken()` (Clerk JS, per ADR-0019).
2. **In-chat side panel** (WI-014) — opens on the right rail when the user clicks "Open document" inside a chat. Uses an iframe (`https://doc-gen.datameesters.nl/iframe-embed.html?docId=...`) with a typed postMessage RPC client at `src/lib/integrations/docGen/iframeClient.ts`. The chat's `executeTool` socket handler routes the model's `docgen_*` tool calls through this client (so the LLM can edit the open document).

The question that prompted this ADR: should the in-chat side panel also switch to the Web Component, for consistency with the standalone route and with Document-Generator's own ADR-002 (which rejected iframes for the standalone surface)?

## Decision

**Keep the iframe path for the in-chat side panel. Web Component stays for the standalone route.**

Document-Generator's ADR-002 rejected iframes for *its own_ embed surface, where the host page is unknown and the editor is the whole point. For our in-chat side panel, the editor sits next to a Svelte chat tree that is the primary surface; the editor is a secondary tool the model can drive. The trade-offs flip:

- **JS isolation matters more here.** A crash in `rm-doc-generator.js` running in the chatbot's own JS context could break unrelated chat features (the message stream, the slash menu, the model selector). The standalone route has nothing else to break — a crash there is at worst a blank page on `/documents/[id]`. The chat surface is the product; we accept the friction of an iframe to keep its blast radius bounded.
- **Bundle decoupling.** The iframe loads its bundle from doc-gen.datameesters.nl with whatever version doc-gen is shipping today. The chatbot does not have to coordinate releases with doc-gen, and a doc-gen bundle bug never lands in the chatbot's Sentry / browser-cache. The Web Component path *does* couple us — we pay this on `/documents/[id]` deliberately because that route exists only for doc-gen.
- **Typed postMessage RPC is already built and tested.** `iframeClient.ts` is ~200 LOC with 11 unit tests, and the model-driven tool calls (`docgen_propose_edit`, etc.) already flow through it via `executeToolDispatch.ts`. Throwing it away for events-instead-of-postMessage ergonomics that no concrete feature is currently blocked on is busywork.
- **CSS / theme isolation.** Iframes give a hard CSS boundary. Web Components with Shadow DOM are *almost* as good but leak in both directions (CSS custom properties, `:host` selectors interacting with host styles). For the side-panel layout — sized by the host, themed by the host — the iframe is simpler.

The lighter integration that Web Components offer (events instead of postMessage, no separate browser context, same-page DOM access) becomes attractive when we want one of:

- An editor rendered **inline inside a chat message bubble** rather than the right-rail panel. Iframes make sub-message embedding awkward (sizing, scroll, focus stealing).
- **Zero-flicker theme/font propagation** between chat and document. The current iframe approach re-applies theme after mount.
- The document editor needs to **share Svelte stores** with the chat (e.g. shared selection, shared focus management, drag-drop between chat and doc).

None of those are on the roadmap today. When one of them lands we revisit; until then, the iframe stays.

## Alternatives considered

| Option                                                                                          | Why rejected                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Switch the in-chat panel to the Web Component now, for consistency with the standalone route.** | Real work (re-wire `executeToolDispatch`, replace `iframeClient.ts`, redo `panelLifecycle.ts`'s iframe-mount waiting, redo 11 unit tests, plumb `auth-token` reactivity) for ergonomics no concrete feature is blocked on. Loses the JS isolation that the chat surface — being the product — benefits from.    |
| **Switch the standalone route to iframe, for consistency the other way.**                       | Document-Generator's ADR-002 explicitly rejected iframes for that surface (heavier, harder to share session, awkward layout, more friction for the read+write API). Re-creating that decision against the upstream project's call would be churn.                                                                |
| **Status quo — both surfaces, both contracts.**                                                 | What this ADR codifies. Each surface uses the embedding mode that fits its constraints; the duplicated integration surface is the explicit cost we pay for letting each context optimise.                                                                                                                       |

## Consequences

- The chatbot maintains two integration paths into doc-gen (`DocGenEmbed.svelte` + `docGenAuth.ts` for the standalone route; `panelLifecycle.ts` + `iframeClient.ts` + `store.ts` + `executeToolDispatch.ts` for the in-chat panel). Bug fixes that apply to both — e.g. the chat→doc-gen `POST /documents` mint in `chatMeta.ts` — must be applied to both call sites. As of this ADR only the iframe path touches `chatMeta.ts`; the standalone route gets the docId from the URL.
- The iframe path keeps an extra HTTP round-trip on first open (`iframe-embed.html` shell + bundle). This is amortised — once loaded, subsequent opens within the same browser session reuse the cached bundle.
- When the model invokes a `docgen_*` tool while the panel is closed, the executeTool handler returns "no active client" — same as today. The standalone route doesn't currently consume the same socket-routed tool calls; if we want LLM-driven edits on `/documents/[id]` we have to extend the dispatch to address a Web Component client too. Future work, not in scope here.

## Revisit triggers

Open this ADR back up if any of the following becomes a concrete requirement:

- Render the editor inside a single chat message bubble (sub-message embed).
- Drag-and-drop content from a chat message into the open document, or vice versa.
- Document editor needs to subscribe to a chatbot store directly (e.g. current selected model, active project pill state).
- Zero-flicker theme handover during a Settings/General theme change while the panel is open.

Until then, the two-path topology stands.
