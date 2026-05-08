# Branded frontend — roadmap

**Date:** 2026-05-09
**Status:** Living plan
**Parent ADR:** [0012-frontend-strategy.md](../../06-adr/0012-frontend-strategy.md)
**Lineage:**
- 2026-03-31 — [Phase A1+A2: fork, brand, auth](2026-03-31-phase-a1-a2-fork-brand-auth.md)
- 2026-04-17 — [Brand Pass 2 spec](../specs/2026-04-17-brand-pass-2.md) ([baseline](../specs/2026-04-17-brand-pass-2-baseline.json) / [after](../specs/2026-04-17-brand-pass-2-after.json))
- 2026-05-09 — this doc

## Why this exists

Brand work has been shipping in waves. Phase A1+A2 set the palette and splash. Brand Pass 2 closed nine specific gaps (manifest, banner, avatars, greeting, etc.). The 2026-05-09 session shipped three more PRs (admin/settings i18n sweep, auth surface, maskable PWA icon). Each wave was scoped tightly and ad-hoc. With more brand surfaces still on the list and the user asking *"FULLY Ruimtemeesters brand"*, this doc captures **where we are**, **what's left**, and **what order to take it in** — so the next session doesn't re-plan from scratch.

This is a living plan, not a one-shot spec. When a tier completes, mark it done; when a surface gets re-prioritised, edit in place.

## Hard constraints (inherited from ADR-0012 §3)

These are not negotiable for any brand-tier work:

1. **Single feature branch per surface, revertable at `git revert` level.** Future Ralph (or the next OpenWebUI upstream sync) must be able to peel a brand change off cleanly.
2. **No fork-wide CSS rewrite.** Theme overrides via CSS variables in `src/lib/themes/ruimtemeesters.css` extend the existing approach — they don't replace OWUI's component classes.
3. **Future OpenWebUI upstream syncs must not be made harder.** Every Svelte source edit is rebase debt; minimise.
4. **No new i18n keys** unless absolutely necessary. New keys force `npm run i18n:parse` regen across all 60 locale files (per `feedback_i18n_regen_after_new_keys.md`). Override existing key values instead.
5. **Major UX redesign or chat-flow re-flow is out of scope.** This is a rebrand, not a rebuild.

## Brand palette (canonical — locked in `ruimtemeesters.css`)

| Token | Hex | Use |
|---|---|---|
| Klein Blue | `#002EA3` | Primary actions, accents, theme color, maskable bg |
| Smart White | `#F7F4EF` | Light-mode background, light-mode body |
| Raisin Black | `#161620` | Dark surfaces, sidebar, dark-mode tab color |
| Violet | `#7F00FF` | Secondary accents, dark-mode shimmer |
| Pumpkin | `#F37021` | Warnings / CTAs (declared, sparingly used) |
| Lion | `#9C885C` | Tertiary, light-mode shimmer |
| Mystified | `#C3D7C1` | Success states (declared, sparingly used) |

Pumpkin / Lion / Mystified are declared but underused — Tier 3 work could give them more surface coverage where the colour is semantically right.

## Status — what's already shipped

### Phase A1+A2 (commit `c38504d74`, ~2026-03-31)
- Brand palette established in CSS theme
- Splash screen
- Prompt suggestions

### Brand Pass 2 (~2026-04-17, all nine criteria green)
- ✅ `WEBUI_FAVICON_URL` fixed (pointed at real `/brand-assets/icon-blue.png`)
- ✅ Custom PWA manifest at `/brand-assets/rm-manifest.json`
- ✅ Persistent trust banner (`Besloten werkomgeving voor Ruimtemeesters · Data wordt niet gedeeld met LLM-providers`)
- ✅ `DEFAULT_MODELS=gemini.gemini-2.5-flash-lite`
- ✅ Five distinct assistant SVG avatars
- ✅ `ENABLE_COMMUNITY_SHARING=false`
- ✅ Personalised greeting (`Hoi {firstName}, waarmee kan ik je vandaag helpen?`)
- ✅ About modal RM copy (`Gebouwd op Open WebUI`)
- ✅ Gemini connection seed script

### 2026-05-09 session
- ✅ **#62** — Admin/settings i18n sweep: 14 stock "Open WebUI" strings rebranded across en-US + nl-NL, value-cleared in 56 other locales for fallback. No new i18n keys, no Svelte touched.
- ✅ **#63** — Auth/sign-in surface: logo paths swapped from `/static/favicon.png` → `/brand-assets/icon-blue.png` (light) and `/brand-assets/icon-white.png` (dark); onboarding-trust copy corrected (the stock string was factually wrong for our deployment).
- ✅ **#64** — Maskable PWA icon: dedicated 512×512 maskable variant on Klein Blue safe-zone bg; manifest sizes claim corrected from a fabricated `500x500` to actual `512x512`.

## Remaining surfaces — by upstream-merge cost

Order matters: take the cheapest tier first. Stop when ROI bottoms out.

### Tier 1 — i18n-value / asset-only (zero or near-zero rebase cost)

| Surface | What | Estimated diff |
|---|---|---|
| **OnBoarding modal** | First-time admin setup flow (`src/lib/components/OnBoarding.svelte`). Inspect for stock OWUI strings + logo paths same as the auth page work in #63. | i18n value overrides + ≤10-line logo path swap |
| **`favicon-dark.png` for the browser tab** | Currently the only dark-mode path swap that's *not* yet on `/brand-assets/icon-white.png` — the auth page got swapped in #63 but `static/favicon.png` is still the OWUI default for the actual browser tab favicon. | 1-line `WEBUI_FAVICON_URL` env change in compose, OR add a dark-favicon env var if OWUI supports one |
| **Settings → General "Manage Open WebUI"** | Quick re-grep — anything I missed in #62's audit? Run the same scan one more time on a fresh checkout. | Likely 0–3 more strings |
| **Splash text / loader copy** | The splash image is branded but any text that flashes during boot may be stock OWUI-flavored. | i18n only, if anything |

**Estimated PRs:** 2–3 small ones. Total work: <1 hour.

### Tier 2 — Minimal Svelte edits (≤20 lines per surface, anchored well for upstream merges)

| Surface | What | Cost |
|---|---|---|
| **Sidebar / chat list** | Top of sidebar shows OWUI-default chrome. Add RM logo or wordmark above the new-chat button; brand the empty-state copy when no chats exist. | One Svelte file, ~10–15 lines |
| **Top bar / model picker chrome** | The chat header has the model picker + share/menu icons. Currently uses default styling — could pick up brand colour for active states beyond what `.bg-blue-600` overrides catch. | Theme CSS extension, possibly small Svelte tweaks |
| **Mobile bottom-nav** | If OWUI exposes a mobile-specific nav, brand it consistently with desktop sidebar | Survey first; may already inherit theme |
| **OnBoarding trust copy expansion** | Beyond the one line we fixed in #63, the OnBoarding component may have other "locally hosted server" claims that need the same treatment | i18n only if all keys exist |
| **Per-surface empty states** | Notes, Knowledge, Workspace — each section has its own empty placeholder. Brand voice consistency. | i18n only for copy; Svelte if illustrations/icons need swapping |

**Estimated PRs:** 3–5. Per surface: 1–2 hours.

### Tier 3 — Theme depth (CSS-only, but wider blast radius)

| Surface | What | Cost |
|---|---|---|
| **Pumpkin / Lion / Mystified surface coverage** | Currently the three under-used brand colors only appear in the shimmer animation. Map them onto: warning toasts (Pumpkin), tertiary text (Lion), success toasts (Mystified). All via `ruimtemeesters.css` overrides on existing OWUI utility classes. | One file, ≤30 lines added |
| **Focus ring / hover state coverage** | `bg-blue-600` is overridden but `bg-blue-500`, `bg-blue-700`, `text-blue-*` variants may render OWUI default in places we missed. Sweep. | One file, ≤20 lines added |
| **Dark mode polish** | `.dark` variants for selection / scrollbar are wired; verify across less-trafficked surfaces (modals, tooltips, code blocks). | One file, varies |

**Estimated PRs:** 1 wider sweep PR or 2–3 small ones. Total: ~2 hours.

### Tier 4 — Larger Svelte / structural work (high rebase cost — gate on real ROI)

| Surface | Why caution | If we do it |
|---|---|---|
| **Workspace UI** (Models / Prompts / Tools / Functions) | Lots of OWUI-Community vibes baked in. We hid community sharing but the chrome and layout are stock. Real Svelte work. | Only if the user identifies this as a daily-use surface for advisors |
| **Chat input area / message bubbles** | Heavily styled by OWUI; restyle = real conflict surface | Only if a specific UX pain emerges |
| **Document viewer** | When files are referenced inline, the viewer is stock | Only if document-grounded chat becomes a primary flow |
| **Settings panels themselves** | Beyond the labels (which #62 brushed), the *layout* is OWUI. | Only for the most-visible panels (e.g. Account) |

**Estimated PRs:** depends on which surfaces graduate from "stock is fine" to "must rebrand".

## Out of scope (explicit — not deferred, **not** doing)

- **Major UX redesign** — this is the rebrand, not a rebuild
- **Marketing pages / landing site** — separate concern, separate site
- **Translating the rest of the admin panel into Dutch** — ADR-0012 §3 defers this as "huge surface, separate effort"
- **Geoportaal custom AI surface** — covered by [ADR-0011](../../06-adr/0011-service-pattern-embedded-ai-surfaces.md), not OWUI rebrand
- **Email templates** — the audit found none in the codebase; either OWUI doesn't ship transactional email here, or it's routed via Clerk

## Naming convention for brand-pass PRs

Pattern observed across this lineage; recommended for next:

- `feat(brand): <surface>` — a single surface (e.g. `feat(brand): brand the auth/sign-in surface` for #63)
- `fix: address bugbot review — <summary>` — remediation pushes (e.g. `fix: address bugbot review — locale fallback + grammar nit`)
- Branch name: `feat/brand-<surface-noun>` (e.g. `feat/brand-onboarding-modal`, `feat/brand-sidebar-chrome`)
- Each PR cites the relevant tier from this doc, calls out the constraint(s) it honours, and explicitly lists what is NOT in the diff to keep scope tight.

## What "FULLY branded" means

A pragmatic definition for this codebase, given the constraints:

1. **No stock "Open WebUI" string anywhere a real user sees** — copy, manifest, titles, splash, About. *Mostly there as of 2026-05-09.*
2. **No stock OpenWebUI brand mark anywhere visible** — favicon, manifest icons, splash, auth logo, sidebar logo. *Mostly there; sidebar logo + browser tab favicon are the last gaps.*
3. **Brand palette applied to every active state a user notices** — buttons, links, focus rings, scrollbars, selection. *Largely done via `ruimtemeesters.css`; Tier 3 sweep would close edge cases.*
4. **Brand voice in copy that matters** — empty states, sign-in, trust banner, About. *Done for chat/auth; OnBoarding is the last surface.*

What "fully" does **not** mean:
- Translating every admin string into Dutch
- Replacing OWUI's chrome with custom Svelte
- Building a different UI

That's a rebuild, not a rebrand. ADR-0012 explicitly opted out of that path.

## Suggested next move

Tier 1 sweep, single PR: pick up the OnBoarding modal + grep for any "Open WebUI" leftovers + verify the browser-tab favicon is truly using the RM mark in dark mode. ≤1 hour, all i18n value overrides + 1–2 env vars + ≤10 Svelte lines if any.

After that, decide based on what's actually visible: continue with Tier 2 (sidebar chrome) or stop and ship.
