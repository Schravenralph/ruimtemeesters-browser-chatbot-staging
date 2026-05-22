"""
title: Skills Context
author: Ruimtemeesters
date: 2026-05-15
version: 1.0.0
license: MIT
description: Inject the active persona's mandatory skills from rm-skills into the system prompt before the LLM call.
"""

# Sibling of bopa_session_context.py and memory_recall_context.py. Same
# async-httpx + per-key cache shape. At chat start this filter resolves
# the active persona from the request model id (or metadata), calls
# `GET /api/v1/skills?persona={persona}` on rm-skills, filters down to
# `mandatory: true` entries, fetches each one's `skill_md` body, and
# injects a `<skills><skill name="X" ...>{body}</skill></skills>` block
# into messages[0]. Fails open on any HTTP error — chat proceeds without
# injection. v1 is mandatory-only; on-demand pulls go through the
# Skills MCP (separate spec).

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# Legacy / capitalised model ids the seed scripts use today. The rm-skills
# service exposes personas in lower-kebab form, so we map both shapes here.
# Append entries when a new persona-id naming convention shows up.
_PERSONA_MAP = {
    'rm-assistent': 'ro-assistent',
    'rm-ro-assistent': 'ro-assistent',
    'rm-juridisch-assistent': 'juridisch-assistent',
    'rm-commercieel-assistent': 'commercieel-assistent',
    'ro-assistent': 'ro-assistent',
    'juridisch-assistent': 'juridisch-assistent',
    'commercieel-assistent': 'commercieel-assistent',
}


def _resolve_persona(model_id: str, metadata: dict | None) -> str:
    """Resolve the active persona slug from request body / metadata.

    Order:
      1. metadata['model']['info']['meta']['persona'] (explicit override)
      2. Hardcoded map (handles `RO-Assistent` capitalisation + `rm-` prefix)
      3. Bare model id, lowercased, after stripping `rm-` prefix

    Returns empty string when nothing usable is present — the inlet then
    no-ops cleanly.

    Pure function. Mirrored as a module-level helper so tests can call
    it without instantiating Filter.
    """
    if isinstance(metadata, dict):
        meta_path = (
            metadata.get('model', {}).get('info', {}).get('meta', {}) if isinstance(metadata.get('model'), dict) else {}
        )
        if isinstance(meta_path, dict):
            persona = meta_path.get('persona')
            if isinstance(persona, str) and persona:
                return persona.strip().lower()

    if not model_id:
        return ''

    lowered = model_id.strip()
    # Direct hit on the map (handles `RO-Assistent` → `ro-assistent`).
    if lowered in _PERSONA_MAP:
        return _PERSONA_MAP[lowered]
    lowered_lc = lowered.lower()
    if lowered_lc in _PERSONA_MAP:
        return _PERSONA_MAP[lowered_lc]

    # Fall-through: strip `rm-` prefix and return lowercased.
    if lowered_lc.startswith('rm-'):
        return lowered_lc[len('rm-') :]
    return lowered_lc


def _format_skills_block(skills: list[dict], persona: str, max_chars: int) -> str:
    """Render the system-prompt block. Pure function — no I/O.

    Wraps every skill body in `<skill name="X" mandatory="true" persona="Y">`
    and groups them in a single `<skills>` envelope (mirrors how Claude
    Code wraps skill content). Truncates each body to max_chars to guard
    against a runaway markdown file blowing the prompt budget.
    """
    if not skills:
        return ''
    parts: list[str] = ['\n\n<skills>']
    for skill in skills:
        name = skill.get('name') or '?'
        body = skill.get('skill_md') or ''
        if max_chars and len(body) > max_chars:
            body = body[:max_chars]
        parts.append(f'<skill name="{name}" mandatory="true" persona="{persona}">\n{body}\n</skill>')
    parts.append('</skills>')
    return '\n'.join(parts)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=20,
            description=(
                'Filter priority (lower = earlier). Runs after the memory filters '
                '(10/11/12) so injected skills see the recalled context.'
            ),
        )
        skills_url: str = Field(
            default='http://rm-skills:4101',
            description='rm-skills HTTP base URL (compose-internal). The filter appends /api/v1/skills paths.',
        )
        skills_token: str = Field(
            default='',
            description='Optional bearer token for rm-skills. Empty disables the Authorization header.',
        )
        timeout_ms: int = Field(
            default=1500,
            description='HTTP timeout for the rm-skills calls. The filter is a no-op on timeout.',
        )
        target_models: str = Field(
            default='rm-assistent,ro-assistent,juridisch-assistent,commercieel-assistent,RO-Assistent,Juridisch-Assistent,Commercieel-Assistent',
            description='Comma-separated list of model IDs the filter should fire for. Other models are no-ops.',
        )
        cache_ttl_s: int = Field(
            default=60,
            description=(
                'Per-(persona, user) cache TTL. The Skills corpus changes infrequently; 60s keeps cold paths '
                'cheap without making admin edits invisible for long.'
            ),
        )
        enabled: bool = Field(
            default=True,
            description='Master kill switch (admin-level). Disable to short-circuit all injection.',
        )
        max_skill_chars: int = Field(
            default=50000,
            description=(
                'Per-skill body cap. Skills longer than this get truncated in the injection — guards against '
                'a runaway markdown file blowing the prompt budget.'
            ),
        )
        max_skills: int = Field(
            default=5,
            description=(
                'Max number of mandatory skills injected per persona. Above this, only the first N are '
                'injected and a warning is logged — protects token cost when many skills become mandatory.'
            ),
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True,
            description='Enable Skills Context injection for this user. Disable to opt out.',
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        # _cache: dict[(persona, user_id), tuple[expires_epoch, block_or_None]]
        # None caches a "no mandatory skills" / "fetch failed" result to
        # avoid hammering rm-skills on every turn of a chat that has no
        # injection to do.
        self._cache: dict[tuple[str, str], tuple[float, str | None]] = {}

    # ----- helpers (instance methods so tests can patch them per-instance) -----

    def _now(self) -> float:
        return time.time()

    def _model_id_from_metadata(self, body: dict, metadata: dict | None) -> str:
        if isinstance(metadata, dict):
            mid = metadata.get('model_id') or (metadata.get('model') or {}).get('id')
            if mid:
                return str(mid)
        return str(body.get('model') or '')

    def _user_opted_out(self, user: dict) -> bool:
        if not isinstance(user, dict):
            return False
        user_valves = user.get('valves')
        if isinstance(user_valves, self.UserValves):
            return not user_valves.enabled
        if isinstance(user_valves, dict):
            return user_valves.get('enabled') is False
        return False

    def _model_in_scope(self, body: dict, metadata: dict | None) -> bool:
        targets = {m.strip() for m in (self.valves.target_models or '').split(',') if m.strip()}
        if not targets:
            return True
        return self._model_id_from_metadata(body, metadata) in targets

    def _headers(self, user_email: str) -> dict[str, str]:
        headers: dict[str, str] = {'Accept': 'application/json'}
        if self.valves.skills_token:
            headers['Authorization'] = f'Bearer {self.valves.skills_token}'
        if user_email:
            # rm-skills hasn't standardised on a header yet, but the
            # other RM MCPs use X-Forwarded-User for end-user identity —
            # mirror that here so the server has a hook for future
            # per-user scoping (Phase D).
            headers['X-Forwarded-User'] = user_email
        return headers

    async def _fetch_skill_list(self, client: httpx.AsyncClient, persona: str, user_email: str) -> list[dict]:
        """GET /api/v1/skills?persona={persona}. Returns raw list (any
        mandatory flag handling happens at the caller)."""
        url = f'{self.valves.skills_url.rstrip("/")}/api/v1/skills'
        resp = await client.get(url, params={'persona': persona}, headers=self._headers(user_email))
        resp.raise_for_status()
        # rm-skills returns either `{skills: [...]}` (canonical) or a
        # bare list (some early endpoints). Accept both.
        data = resp.json() if callable(getattr(resp, 'json', None)) else None
        if isinstance(data, dict):
            skills = data.get('skills')
        else:
            skills = data
        if not isinstance(skills, list):
            return []
        return [s for s in skills if isinstance(s, dict)]

    async def _fetch_skill_body(self, client: httpx.AsyncClient, name: str, user_email: str) -> dict | None:
        """GET /api/v1/skills/:name. Returns the parsed payload (must include
        `skill_md`) or None on any error."""
        url = f'{self.valves.skills_url.rstrip("/")}/api/v1/skills/{name}'
        try:
            resp = await client.get(url, headers=self._headers(user_email))
            resp.raise_for_status()
            data = resp.json() if callable(getattr(resp, 'json', None)) else None
        except (httpx.HTTPError, ValueError) as e:
            log.warning('skills_context: skill body fetch failed for %s: %s', name, e)
            return None
        if not isinstance(data, dict):
            return None
        return data

    async def _build_block_for_persona(self, persona: str, user_email: str) -> str | None:
        """Single round-trip orchestration: list mandatory skills → fetch
        each body → format the block. Returns None when there's nothing
        to inject or any non-recoverable error occurs."""
        try:
            async with httpx.AsyncClient(timeout=self.valves.timeout_ms / 1000.0) as client:
                skills_list = await self._fetch_skill_list(client, persona, user_email)
                mandatory = [s for s in skills_list if bool(s.get('mandatory'))]
                if not mandatory:
                    return None
                if len(mandatory) > self.valves.max_skills:
                    log.warning(
                        'skills_context: %d mandatory skills for persona %s exceeds cap %d; truncating to first %d',
                        len(mandatory),
                        persona,
                        self.valves.max_skills,
                        self.valves.max_skills,
                    )
                    mandatory = mandatory[: self.valves.max_skills]
                bodies: list[dict] = []
                for skill in mandatory:
                    name = skill.get('name')
                    if not isinstance(name, str) or not name:
                        continue
                    payload = await self._fetch_skill_body(client, name, user_email)
                    if payload and payload.get('skill_md'):
                        # Merge the list entry's metadata (mandatory flag) with
                        # the body payload — the body endpoint returns skill_md
                        # plus its own metadata, but we treat the list as the
                        # source of truth for mandatory.
                        bodies.append({**payload, 'name': name})
        except (httpx.HTTPError, ValueError) as e:
            log.warning('skills_context: rm-skills list call failed for persona %s: %s', persona, e)
            return None
        if not bodies:
            return None
        return _format_skills_block(bodies, persona, self.valves.max_skill_chars)

    async def _block_for_user(self, persona: str, user_id: str, user_email: str) -> str | None:
        """Cached lookup. Key is (persona, user_id) — Phase D will add
        user-scoped skills, and we want to invalidate independently per
        user when that lands."""
        if not persona or not user_id:
            return None
        key = (persona, user_id)
        cached = self._cache.get(key)
        if cached and cached[0] > self._now():
            return cached[1]
        block = await self._build_block_for_persona(persona, user_email)
        # Cache both hits and misses — a "no mandatory skills" result is
        # just as valuable as a positive one for skipping the next RPC.
        self._cache[key] = (self._now() + self.valves.cache_ttl_s, block)
        return block

    def _inject_block(self, body: dict, block: str) -> None:
        """Append block to the existing system message, or insert a new
        system message at position 0 when the body has none yet."""
        messages = body.get('messages') or []
        if not (isinstance(messages, list) and messages):
            body['messages'] = [{'role': 'system', 'content': block.lstrip()}]
            return
        if messages[0].get('role') == 'system':
            messages[0] = {
                **messages[0],
                'content': (messages[0].get('content') or '') + block,
            }
        else:
            messages = [{'role': 'system', 'content': block.lstrip()}] + messages
        body['messages'] = messages

    # ----- inlet entry point -----

    async def inlet(
        self,
        body: dict,
        __user__: dict | None = None,
        __metadata__: dict | None = None,
        **_: Any,
    ) -> dict:
        try:
            if not self.valves.enabled:
                return body
            user = __user__ or {}
            user_id = str(user.get('id') or '')
            user_email = str(user.get('email') or '').strip()
            if not user_id or self._user_opted_out(user):
                return body
            if not self._model_in_scope(body, __metadata__):
                return body
            model_id = self._model_id_from_metadata(body, __metadata__)
            persona = _resolve_persona(model_id, __metadata__)
            if not persona:
                return body
            block = await self._block_for_user(persona, user_id, user_email)
            if block:
                self._inject_block(body, block)
        except Exception as e:
            # Filters must never break the chat. Log and pass body through.
            log.warning('skills_context: unexpected error, passing body through: %s', e)

        return body
