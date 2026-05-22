"""
title: Memory Recall Context
author: Ruimtemeesters
date: 2026-05-03
version: 1.0.0
license: MIT
description: Inject memories relevant to the latest user message into the system prompt before the LLM call.
"""

# Sibling of bopa_session_context.py. Same async-httpx + per-user cache shape.
# This filter calls `recall_memory` on rm-mcp-memory with the user's last
# message as the FTS query and injects the top-N descriptions/snippets into
# the system prompt — so the model sees what's been saved before it answers.
# The filter does not fetch full memory bodies; the model can call
# `get_memory(name)` itself if it needs the full content. Index-then-fetch
# keeps the system prompt small.

import hashlib
import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


def _last_user_message(messages: list[dict]) -> str:
    """Pick the most recent user message from the chat. Returns empty string
    when the body has no user turn yet — which short-circuits the RPC.

    Pure function; the inlet body is read-only here."""
    if not isinstance(messages, list):
        return ''
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get('role') != 'user':
            continue
        content = msg.get('content')
        if isinstance(content, str):
            return content.strip()
        # OpenAI-style content arrays (text + image parts)
        if isinstance(content, list):
            parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
            return ' '.join(parts).strip()
    return ''


def _parse_mcp_response(text: str) -> dict:
    """Parse an MCP HTTP response body. The Streamable HTTP transport
    returns either pure JSON (rare — error paths) OR Server-Sent-Events
    framed as `event: message\\ndata: {...}` (the normal path when
    `Accept: application/json, text/event-stream` is requested, which the
    MCP server now mandates — Issue #49 follow-up). We accept both.

    Multiple SSE events are tolerated: the last event whose data is
    valid JSON wins. Non-JSON data events (e.g. session-management
    notifications, keep-alives) are skipped silently rather than
    aborting the parse — a strict json.loads inside the loop would lose
    a valid result that comes after a non-JSON event (Bugbot review on
    PR #52).

    Pure function. Raises ValueError if no data event yielded valid JSON.
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


def _format_block(matches: list[dict]) -> str:
    """Render the system-prompt block. Pure function — no I/O.

    Dutch-language to match the assistant's response language. Lists name +
    description per match (no snippets, to keep the block short); the model
    follows up with `get_memory(name)` for full content when it wants the body.
    """
    lines: list[str] = [
        '\n\n---',
        'EERDER OPGESLAGEN MEMORIES (relevant voor deze vraag — automatisch ingeladen)',
    ]
    for m in matches:
        name = m.get('name') or '?'
        description = (m.get('description') or '').strip()
        scope = m.get('scope') or '?'
        if description:
            lines.append(f'- `{name}` ({scope}): {description}')
        else:
            lines.append(f'- `{name}` ({scope})')
    lines.append('Roep `get_memory({name})` aan voor de volledige inhoud van een memory wanneer die nodig is.')
    return '\n'.join(lines)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=11,
            description=(
                'Filter priority (lower = earlier). Run after bopa_session_context (priority 10) '
                'so BOPA state lands first when both apply.'
            ),
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
            description='HTTP timeout for the recall_memory RPC. The filter is a no-op on timeout.',
        )
        cache_ttl_s: int = Field(
            default=30,
            description=(
                'Per-(user, query) cache TTL. Avoids hammering the MCP when an advisor sends the '
                'same prompt twice (e.g. retry, edit-and-resend).'
            ),
        )
        target_models: str = Field(
            default='rm-assistent',
            description='Comma-separated list of model IDs the filter should fire for. Other models are no-ops.',
        )
        limit: int = Field(
            default=5,
            description='Max memories to surface in the system prompt. Higher = more context, more tokens.',
        )
        min_query_chars: int = Field(
            default=4,
            description=(
                'Skip the RPC for very short queries ("hi", "ok") which produce noisy FTS hits. '
                'Below this length the filter is a no-op.'
            ),
        )
        enabled: bool = Field(
            default=True,
            description='Master kill switch (admin-level). Disable to short-circuit all injection.',
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True,
            description='Enable memory recall injection for this user. Disable to opt out.',
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        # _cache: dict[(user_id, query_hash), tuple[expires_epoch, block_or_None]]
        # None means "we recalled recently and got zero matches" — also cached
        # to avoid re-querying on no-op turns.
        self._cache: dict[tuple[str, str], tuple[float, str | None]] = {}

    # ----- helpers -----

    def _now(self) -> float:
        return time.time()

    def _query_hash(self, query: str) -> str:
        return hashlib.sha256(query.encode('utf-8')).hexdigest()[:16]

    async def _recall(self, query: str, user_email: str) -> list[dict]:
        """Call recall_memory on rm-memory. Returns matches list (possibly empty).

        The X-Forwarded-User header carries the end-user's email; rm-memory's
        auth layer (packages/memory/src/auth.ts) maps it to a `clerk:<email>`
        identity and applies the per-caller scoping predicate server-side.
        That replaces the older client-side post-filter on owner_user_id —
        which was wrong anyway, since OpenWebUI's user.id is a UUID while the
        MCP stores `clerk:<email>` (Issue #49).

        Async because OpenWebUI awaits the inlet on its main asyncio loop —
        a sync HTTP call would block other coroutines for the timeout window.
        """
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'recall_memory',
                'arguments': {'query': query, 'limit': self.valves.limit},
            },
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
            log.warning('memory_recall_context: rm-memory RPC failed: %s', e)
            return []

        # MCP tools/call response shape: {result: {content: [{type: text, text: "<json>"}]}}
        try:
            result = data.get('result') or {}
            content = result.get('content') or []
            if not content:
                return []
            text = (content[0] or {}).get('text', '')
            blob = json.loads(text) if text else {}
        except (ValueError, AttributeError, IndexError, TypeError) as e:
            log.warning('memory_recall_context: malformed MCP response: %s', e)
            return []

        matches = blob.get('matches') if isinstance(blob, dict) else None
        if not isinstance(matches, list):
            return []
        return [m for m in matches if isinstance(m, dict)]

    def _evict_expired(self) -> None:
        """Remove all expired cache entries to prevent unbounded dict growth."""
        now = self._now()
        expired = [k for k, (expires, _) in self._cache.items() if expires <= now]
        for k in expired:
            del self._cache[k]

    async def _block_for_query(self, user_id: str, user_email: str, query: str) -> str | None:
        """Cached lookup. Returns None when there are no matches or on RPC failure.

        Cache is keyed on (user_id, query_hash) — the OpenWebUI user.id is
        stable per session and avoids cache collision across users sharing a
        machine. The email is used only to build X-Forwarded-User for the
        outbound RPC."""
        if not user_id or not query:
            return None
        if len(query) < self.valves.min_query_chars:
            return None
        key = (user_id, self._query_hash(query))
        cached = self._cache.get(key)
        if cached and cached[0] > self._now():
            return cached[1]
        matches = await self._recall(query, user_email)
        block = _format_block(matches) if matches else None
        self._cache[key] = (self._now() + self.valves.cache_ttl_s, block)
        self._evict_expired()
        return block

    def _model_id_from_metadata(self, body: dict, metadata: dict | None) -> str:
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

    def _inject_block(self, body: dict, block: str) -> None:
        """Append block to the existing system message, or insert one."""
        messages = body.get('messages') or []
        if not (messages and isinstance(messages, list)):
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
            query = _last_user_message(body.get('messages') or [])
            if not query:
                return body
            block = await self._block_for_query(user_id, user_email, query)
            if block:
                self._inject_block(body, block)
        except Exception as e:
            # Filters must never break the chat. Log and pass body through.
            log.warning('memory_recall_context: unexpected error, passing body through: %s', e)

        return body
