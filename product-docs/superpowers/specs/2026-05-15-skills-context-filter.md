# skills_context inlet filter

**Date:** 2026-05-15
**Status:** Draft (proactive-brainstorm Phase 3)
**Tracking:** Browser-Chatbot #108, Skills #11, MCP-Servers #98

## Goal

Add `rm-tools/filters/skills_context.py` — an OpenWebUI inlet filter that, at chat start, fetches the active persona's **mandatory** skills from `rm-skills:4101` and injects each one's `skill_md` body into the system prompt as a `<skill name="...">...</skill>` block.

This is the _minimum_ skill-loading path. On-demand pulls go through the Skills MCP tools (separate spec `2026-05-15-skills-mcp-package.md`).

## Scope (v1)

- Resolve **active persona** from request body or model metadata
- Call `GET http://rm-skills:4101/api/v1/skills?persona={persona}`
- Filter to `mandatory: true` entries only
- For each, fetch `GET /api/v1/skills/:name` for the body
- Inject as `<skill name="X">{skill_md}</skill>` blocks into `messages[0]` system content (append, mirroring memory filters)
- Fail-open on any HTTP error
- Cache per-persona result in-process for 60s (mirrors the rate at which Skills corpus actually changes)

**Out of scope for v1:** keyword-triggered injection, user-scope skills (no Phase D yet), persona overrides via valves.

## Design choices applied

| #   | Choice                                                                                  | Rationale                                                                                 |
| --- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1   | Hybrid (always-inject mandatory + MCP for the rest)                                     | Phase 2 design table                                                                      |
| 2   | Frontmatter-driven persona filter                                                       | Already supported by Skills service                                                       |
| 6   | Filter priority 20                                                                      | After memory filters (10/11/12) so skill sees recalled context                            |
| 7   | Wire on `rm-assistent` AND `RO-Assistent`/`Juridisch-Assistent`/`Commercieel-Assistent` | User flow targets RO; don't entangle with #109                                            |
| 9   | Verify rm-network attachment before changes                                             | Memory filters already reach `rm-mcp-memory:3200` — chatbot must be on rm-network somehow |

## Implementation outline

**Template:** `rm-tools/filters/bopa_session_context.py` (verbatim adaptations only).

```python
class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=20)
        skills_url: str = Field(default='http://rm-skills:4101')
        skills_token: str = Field(default='')
        timeout_ms: int = Field(default=1500)
        target_models: str = Field(default='rm-assistent,ro-assistent,juridisch-assistent,commercieel-assistent')
        cache_ttl_s: int = Field(default=60)
        enabled: bool = Field(default=True)
        max_skill_chars: int = Field(default=50000)

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self._enabled_for_model(body): return body
        persona = self._resolve_persona(body)  # from model id / metadata
        if not persona: return body
        skills_md = await self._fetch_mandatory_skills(persona, __user__)
        if not skills_md: return body
        self._inject(body, skills_md)
        return body
```

**Persona resolution** order:

1. `body['model']` → strip `rm-` prefix → lowercase (e.g. `rm-ro-assistent` → `ro-assistent`)
2. `body['metadata']['model']['info']['meta']['persona']` if set
3. Hardcoded map for legacy ids (`RO-Assistent` → `ro-assistent`)
4. Fall back: skip injection

**Two HTTP calls** per chat (cached): one list, N body fetches. With v1 mandatory skill count likely ≤ 2 per persona, total ≤ 3 round-trips on a cache miss, 0 on hit.

**Async HTTP:** `httpx.AsyncClient` with `timeout_ms / 1000.0`. Never `requests` (memory: `feedback_openwebui_filter_async_http.md`).

**Injection format** (mirrors how Claude Code wraps skill content):

```
<skills>
<skill name="beleidsscan" mandatory="true" persona="ro-assistent">
{full skill_md body}
</skill>
</skills>
```

Appended to existing system message content with a leading `\n\n` separator.

**Cache key**: `(persona, user_id)` — invalidates per user so future per-user skills (Phase D) don't bleed.

## Registration

Add to `rm-tools/register_assistants.py` filter list AND wire to all 4 target personas in their `filterIds` arrays (alongside the 3 existing memory filters).

Add to `scripts/seed-litellm-connection.sh` so the canon RO/Juridisch/Commercieel personas also get the filter.

## Success criteria (measurable)

| #   | Criterion                                                                                            | How to measure                                      |
| --- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| F1  | New chat in RO Assistent with no message → system prompt contains `<skill name="beleidsscan">` block | Log inspection: enable DEBUG, grep `injected skill` |
| F2  | `beleidsscan` body present in injected text (assert length > 8000 chars)                             | Same log inspection                                 |
| F3  | Filter fails open: kill `rm-skills` container, chat still proceeds                                   | Manual test                                         |
| F4  | Cold-path latency overhead < 600ms (filter inlet → model call)                                       | Trace timestamps                                    |
| F5  | Warm-path (cached) overhead < 10ms                                                                   | Trace timestamps                                    |
| F6  | Filter NOT firing on non-target models (e.g. `gpt-oss-models/gemma3:4b` direct)                      | Negative test                                       |
| F7  | Wired on all 4 target personas in production                                                         | `gh pr view` + production smoke                     |

## Validation plan

1. **Unit test** (`backend/test/filters/test_skills_context.py` or wherever existing filter tests live — check pattern first):
   - Mock `httpx.AsyncClient` with fixture rm-skills responses
   - Test: persona resolution from 4 different model id shapes
   - Test: mandatory-only filtering (non-mandatory skill not injected)
   - Test: injection appends rather than replaces existing system message
   - Test: fail-open on 500 / timeout / connection refused
2. **Integration test**: docker-compose up rm-skills + chatbot; submit an actual /api/chat/completions request with model `rm-assistent`; assert response system-prompt content via debug logging.
3. **Production smoke**: deploy, open RO Assistent in chat UI, ask "doe een thematische beleidsscan voor gemeente Utrecht op thema energietransitie", verify model response references the 5-step canon (Phase 1, Phase 2, ... or equivalent step markers from beleidsscan/SKILL.md).

## Comparison to baseline

| Metric                                | Before                | After (target)                   | Method                        |
| ------------------------------------- | --------------------- | -------------------------------- | ----------------------------- |
| Skill content visible to RO Assistent | 0 chars               | ~10,000 chars (beleidsscan body) | Log diff                      |
| Model follows 5-step canon            | Ad-hoc / "improvises" | References ≥ 4 of 5 step markers | Manual review of 3 test chats |
| Chat latency p95 (cold)               | ~X ms baseline        | +600ms acceptable                | Trace before/after            |

## Risks & mitigations

- **R1 — Persona resolution drift**: model ids change between `register_assistants.py` and `seed-litellm-connection.sh`. Mitigation: hardcoded resolution map covers both shapes; warn-log on unknown persona.
- **R2 — Skill content prompt-injection**: corpus skills are git-tracked + reviewed; treat as trusted. Phase D user-scoped skills would change this — explicitly out of v1.
- **R3 — Mandatory skill spam**: if many skills become mandatory for a persona, token cost balloons. Mitigation: hard cap of 5 mandatory skills injected per persona; warn-log if exceeded.
- **R4 — Network**: rm-skills must be reachable from chatbot. Mitigation: verify in Phase 4 before changing compose.

## Out of scope / follow-ups

- Keyword-triggered injection of non-mandatory skills
- User-saved (Phase D) skill injection — needs prompt-injection threat model first
- Skill versioning / rollback
- Telemetry: which skills get pulled via MCP after injection
