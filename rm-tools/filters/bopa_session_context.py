"""
title: BOPA Session Context
author: Ruimtemeesters
date: 2026-05-01
version: 1.0.0
license: MIT
description: Inject the user's most-recent active BOPA session into the system prompt before the LLM call.
"""

# `httpx` is bundled with OpenWebUI (pinned in pyproject.toml). Async client
# is required: OpenWebUI awaits filter inlets on its main asyncio loop, so a
# sync HTTP call would block other coroutines for the duration of the RPC.
# No `requirements:` frontmatter is declared so the plugin loader skips the
# pip-install step on every cold load.

import datetime as dt
import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

PHASE_NAMES = {
    1: 'Haalbaarheid',
    2: 'Strijdigheid',
    3: 'Beleid',
    4: 'Omgevingsaspecten',
    5: 'Onderbouwing',
    6: 'Toetsing',
}

PHASE_SLASH_COMMANDS = {
    1: '/bopa-haalbaarheid',
    2: '/bopa-strijdigheid',
    3: '/bopa-beleid',
    4: '/bopa-omgevingsaspecten',
}


def _parse_mcp_response(text: str) -> dict:
    """Parse an MCP HTTP response body. The Streamable HTTP transport
    returns either pure JSON OR Server-Sent-Events framed as
    `event: message\\ndata: {...}`. The MCP server requires both content
    types to be in the Accept header and picks SSE for the response, so
    this parser handles both shapes.

    Multiple SSE events are tolerated: the last event whose data is
    valid JSON wins. Non-JSON data events (e.g. notifications,
    keep-alives) are skipped silently rather than aborting the parse —
    a strict json.loads inside the loop would lose a valid result that
    comes after a non-JSON event (Bugbot review on PR #52).

    Pure function. Mirrored in `memory_recall_context._parse_mcp_response`
    (duplicated rather than imported because OpenWebUI loads each filter
    as a self-contained module).
    """
    if not text:
        raise ValueError('empty response body')
    stripped = text.lstrip()
    if stripped.startswith('{'):
        return json.loads(stripped)
    last_payload: dict | None = None

    def _try_consume(buf: list[str]) -> None:
        """Attempt to JSON-parse the joined data lines and update the
        accumulator. Non-JSON payloads are skipped, not raised."""
        nonlocal last_payload
        joined = '\n'.join(buf).strip()
        if not joined:
            return
        try:
            parsed = json.loads(joined)
        except ValueError:
            return
        if isinstance(parsed, dict):
            last_payload = parsed

    data_buf: list[str] = []
    for line in text.splitlines():
        if line.startswith('data:'):
            data_buf.append(line[5:].lstrip())
        elif line == '' and data_buf:
            _try_consume(data_buf)
            data_buf = []
    if data_buf:
        _try_consume(data_buf)
    if last_payload is None:
        raise ValueError('SSE body had no JSON data event')
    return last_payload


def _compute_dependencies_met(completed_phases: list[int]) -> list[int]:
    """Mirror of computeDependenciesMet in
    Ruimtemeesters-MCP-Servers/packages/memory/src/phaseDependencies.ts.

    Phase 1 has no prerequisites. Phases 2 and 3 require Phase 1.
    Phases 4, 5 require 1+2+3. Phase 6 requires 1+2+3+4+5.

    The MCP already returns this on get_bopa_session, but list_bopa_sessions
    returns only completed_phases — so the filter recomputes locally to
    avoid a second RPC.
    """
    completed = set(completed_phases)
    ready = []
    if 1 not in completed:
        ready.append(1)
    if 1 in completed:
        if 2 not in completed:
            ready.append(2)
        if 3 not in completed:
            ready.append(3)
    if {1, 2, 3}.issubset(completed):
        if 4 not in completed:
            ready.append(4)
        if 5 not in completed:
            ready.append(5)
    if {1, 2, 3, 4, 5}.issubset(completed):
        if 6 not in completed:
            ready.append(6)
    return ready


def _format_summary(session: dict, others_count: int) -> str:
    """Render the system-prompt block. Pure function — no I/O.

    Keeps the block short and Dutch-language to match the assistant's
    response language (per system prompt richtlijnen).
    """
    sid = session.get('id') or session.get('session_id', '?')
    project_id = session.get('project_id', '?')
    gemeente_code = session.get('gemeente_code', '?')
    completed = session.get('completed_phases', []) or []
    current_phase = session.get('current_phase')

    dependencies_met = _compute_dependencies_met(completed)
    next_phase = dependencies_met[0] if dependencies_met else None

    completed_str = ', '.join(str(p) for p in completed) if completed else 'geen'
    if next_phase is not None:
        slash = PHASE_SLASH_COMMANDS.get(next_phase)
        next_label = f'fase {next_phase} ({PHASE_NAMES.get(next_phase, "?")})'
        if slash:
            next_line = f'Volgende stap: {next_label} — gebruik `{slash}` of `/bopa-status` voor het overzicht.'
        else:
            next_line = (
                f'Volgende stap: {next_label} — MCP-tool nog niet beschikbaar; '
                'gebruik `/bopa-status` voor het overzicht.'
            )
    else:
        next_line = 'Alle 6 fases afgerond.'

    current_str = f'fase {current_phase}/6 actief' if current_phase else 'geen actieve fase'

    block = (
        '\n\n---\n'
        'ACTIEVE BOPA-SESSIE (automatisch ingeladen)\n'
        f'Sessie: {sid} (project {project_id} — gemeente {gemeente_code})\n'
        f'Status: {current_str}; afgeronde fasen: {completed_str}\n'
        f'{next_line}'
    )
    if others_count > 0:
        block += f'\nAndere actieve sessies: {others_count} — gebruik `/bopa-status` om te schakelen.'
    return block


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=10,
            description='Filter priority (lower = earlier). Run before tool-routing filters.',
        )
        mcp_url: str = Field(
            default='http://rm-mcp-memory:3200/mcp',
            description='rm-memory MCP server JSON-RPC endpoint (compose-internal URL).',
        )
        mcp_token: str = Field(
            default='',
            description='Bearer token for the rm-memory MCP. Matches MEMORY_GATEWAY_TOKEN in compose.',
        )
        timeout_ms: int = Field(
            default=800,
            description='HTTP timeout for the list_bopa_sessions RPC. The filter is a no-op on timeout.',
        )
        cache_ttl_s: int = Field(
            default=30,
            description=(
                'Per-user cache TTL. Avoids hammering the MCP when an advisor sends multiple turns in quick succession.'
            ),
        )
        target_models: str = Field(
            default='rm-assistent',
            description='Comma-separated list of model IDs the filter should fire for. Other models are no-ops.',
        )
        max_age_hours: int = Field(
            default=168,
            description=(
                'Skip sessions whose updated_at is older than this many hours. '
                'Default 7 days — guards against an "active" session from months '
                'ago auto-loading because nobody closed it.'
            ),
        )
        enabled: bool = Field(
            default=True,
            description='Master kill switch (admin-level). Disable to short-circuit all injection.',
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True,
            description='Enable BOPA session context injection for this user. Disable to opt out.',
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        # _cache: dict[user_id, tuple[expires_epoch, summary_str_or_None]]
        # None means "we checked recently and no active session exists" — the
        # negative result is also cached to avoid re-querying on no-op turns.
        self._cache: dict[str, tuple[float, str | None]] = {}

    # ----- helpers (instance methods so tests can patch them per-instance) -----

    def _now(self) -> float:
        return time.time()

    def _is_recent(self, session: dict) -> bool:
        """True iff session.updated_at is within max_age_hours of now.

        Sessions older than the cutoff don't auto-load — guards against a
        forgotten "active" row from months ago leaking back into chat. A
        missing or unparseable timestamp is treated as stale (False) so we
        fail closed.
        """
        raw = session.get('updated_at') or ''
        if not raw:
            return False
        try:
            ts = dt.datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.UTC)
        delta_h = (dt.datetime.now(dt.UTC) - ts).total_seconds() / 3600
        return 0 <= delta_h <= self.valves.max_age_hours

    async def _fetch_active_session(self, user_id: str, user_email: str) -> tuple[dict | None, int]:
        """Call list_bopa_sessions on rm-memory. Returns (chosen_session, others_count).

        chosen_session is None when the user has zero active sessions, all
        active sessions are stale (older than max_age_hours), or the RPC
        failed. others_count is the number of additional in-window active
        sessions beyond the chosen one.

        Async because OpenWebUI awaits the inlet on its main asyncio loop —
        a sync HTTP call would block other coroutines for the timeout window.
        """
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': 'list_bopa_sessions', 'arguments': {}},
        }
        headers: dict[str, str] = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }
        if self.valves.mcp_token:
            headers['Authorization'] = f'Bearer {self.valves.mcp_token}'
        if user_email:
            headers['X-Forwarded-User'] = user_email

        try:
            async with httpx.AsyncClient(timeout=self.valves.timeout_ms / 1000.0) as client:
                resp = await client.post(self.valves.mcp_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = _parse_mcp_response(resp.text)
        except (httpx.HTTPError, ValueError) as e:
            log.warning('bopa_session_context: rm-memory RPC failed: %s', e)
            return None, 0

        # MCP tools/call response shape: {result: {content: [{type: text, text: "<json>"}]}}
        # The rm-memory tools return JSON-encoded text in the first content block.
        try:
            result = data.get('result') or {}
            content = result.get('content') or []
            if not content:
                return None, 0
            first = content[0] or {}
            text = first.get('text', '')
            sessions_blob = json.loads(text) if text else {}
        except (ValueError, AttributeError, IndexError, TypeError) as e:
            log.warning('bopa_session_context: malformed MCP response: %s', e)
            return None, 0

        sessions = sessions_blob.get('sessions') if isinstance(sessions_blob, dict) else None
        if sessions is None and isinstance(sessions_blob, list):
            sessions = sessions_blob
        if not isinstance(sessions, list):
            return None, 0

        # Filter by status + recency. The X-Forwarded-User header drives
        # server-side scoping in rm-memory (Issue #49 — the previous
        # client-side `owner_user_id == user_id` post-filter compared an
        # OpenWebUI UUID against the MCP's `clerk:<email>` and never
        # matched). A stale active session is treated as no session.
        active_owned = [
            s for s in sessions if isinstance(s, dict) and s.get('status') == 'active' and self._is_recent(s)
        ]
        if not active_owned:
            return None, 0

        # Sort by updated_at desc; fall back to created_at, then leave order.
        def sort_key(s: dict) -> str:
            return s.get('updated_at') or s.get('created_at') or ''

        active_owned.sort(key=sort_key, reverse=True)
        return active_owned[0], max(0, len(active_owned) - 1)

    async def _summary_for_user(self, user_id: str, user_email: str) -> str | None:
        """Cached lookup. Returns None if no active session or on RPC failure.

        Cache is keyed on the OpenWebUI user.id (stable per session); the
        email is used only to build X-Forwarded-User for the outbound RPC.
        """
        if not user_id:
            return None
        cached = self._cache.get(user_id)
        if cached and cached[0] > self._now():
            return cached[1]
        session, others = await self._fetch_active_session(user_id, user_email)
        summary = _format_summary(session, others) if session else None
        self._cache[user_id] = (self._now() + self.valves.cache_ttl_s, summary)
        return summary

    def _model_id_from_metadata(self, body: dict, metadata: dict | None) -> str:
        """Pull the model id from request body or metadata, however it shows up."""
        if isinstance(metadata, dict):
            mid = metadata.get('model_id') or metadata.get('model', {}).get('id')
            if mid:
                return str(mid)
        return str(body.get('model') or '')

    def _user_opted_out(self, user: dict) -> bool:
        user_valves = user.get('valves') if isinstance(user, dict) else None
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

    def _inject_summary(self, body: dict, summary: str) -> None:
        """Append summary to the existing system message, or insert one."""
        messages = body.get('messages') or []
        if not (messages and isinstance(messages, list)):
            return
        if messages[0].get('role') == 'system':
            messages[0] = {
                **messages[0],
                'content': (messages[0].get('content') or '') + summary,
            }
        else:
            messages = [{'role': 'system', 'content': summary.lstrip()}] + messages
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
            summary = await self._summary_for_user(user_id, user_email)
            if summary:
                self._inject_summary(body, summary)
        except Exception as e:
            # Filters must never break the chat. Log and pass body through.
            log.warning('bopa_session_context: unexpected error, passing body through: %s', e)

        return body
