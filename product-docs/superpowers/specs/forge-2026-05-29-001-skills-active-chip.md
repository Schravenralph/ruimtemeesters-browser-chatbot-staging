# Forge Spec: Skills active chip in chat navbar

**Cycle:** 1 | **Size:** medium

## What

A small chip in the chat navbar that lists the mandatory skills currently
loaded into the LLM's system prompt for the active persona. Hover/click
reveals the skill names with a short description. Driven by the same
`rm-skills` corpus the `skills_context` inlet filter reads from, so the
chip cannot drift from what the LLM actually sees.

## Why

PR #151 made the `skills_context` filter actually deliver mandatory
skill bodies into the system prompt (previously 401-ing silently). But
the injection happens invisibly: a Juridisch advisor has no way to know
`beleidsscan` + `legal-references` are active in this chat. Surfacing
the loaded skills:

- **Builds trust** in the LLM's behavior ("I see why it cited a wetsartikel
  precisely — `legal-references` is loaded.")
- **Helps debug** when a persona seems to "forget" its persona-specific
  guidance — advisors can confirm at a glance whether the skill loaded.
- **Closes the loop** on PR #151: shipping invisible plumbing without a
  visible signal leaves the value on the table.

## Success criteria

1. On the chat page with an active persona (RO / Juridisch / Commercieel),
   the navbar shows a chip "Skills: N" reflecting the actual mandatory
   count rm-skills reports for that persona.
2. Clicking the chip opens a small popover listing each mandatory skill's
   name + 1-line description.
3. When the persona has no mandatory skills (e.g. Commercieel today), the
   chip renders as "Skills: 0" or is hidden (deferred decision — see Not
   doing).
4. The chip and popover work with the rm-skills bearer that the BFF
   already holds (`SKILLS_GATEWAY_TOKEN`); the frontend never sees the
   token.

## Approach

- **BFF endpoint:** `GET /api/v1/skills/active?persona=<slug>` in a new
  `backend/open_webui/routers/rm_skills.py`. Proxies to rm-skills with
  the gateway token, returns `{persona, skills: [{name, description}]}`
  filtered to `mandatory: true`. No skill bodies (those are heavy; the
  filter handles bodies server-side).
- **Frontend:** `src/lib/components/chat/SkillsActiveChip.svelte` —
  reads the current persona from the chat metadata (the same source the
  filter uses), calls the BFF, renders the chip + popover. Placed in
  `Navbar.svelte` next to the `ActiveProjectPill`.
- **Mirror existing patterns:** auth via `localStorage.token`, error
  handling via the existing toast helper, popover via the same Floating
  UI pattern other chips use. Don't introduce new abstractions.

## Not doing

- Showing on-demand (non-mandatory) skills — those are LLM-pulled, not
  pre-loaded, and would mislead.
- Showing skill bodies in the popover — bodies can be 20 KB; popover
  is for orientation, not reading.
- Hiding the chip when count is 0 — a "Skills: 0" chip is itself useful
  feedback that no persona-specific corpus is wired. (Reversible later.)
- Persona switching from inside the popover — out of scope.
- Permissions / per-user opt-out — same surface as the filter; no extra
  controls.
