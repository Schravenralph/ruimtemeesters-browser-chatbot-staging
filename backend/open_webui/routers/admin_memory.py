"""Admin BFF for the Ruimtemeesters memory MCP.

Surfaces `get_adoption_stats` (admin-only cross-user aggregates) over
HTTP so the chatbot frontend can render an ops-dashboard view without
the operator needing prod SSH access. The browser never sees the
admin token: this router holds it server-side via `MEMORY_ADMIN_TOKEN`
and the chatbot's own admin-role check (`get_admin_user`) gates the
endpoint.

Auth shape on the MCP side: `Authorization: Bearer <admin_token>` with
NO `X-Forwarded-User` header — admin callers operate under the
synthetic `system:admin` identity and intentionally bypass per-caller
scoping (see Ruimtemeesters-MCP-Servers/packages/memory/src/identity.ts).
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from open_webui.utils.auth import get_admin_user
from open_webui.utils.mcp_response import extract_tool_result, parse_mcp_response

log = logging.getLogger(__name__)

router = APIRouter()


DEFAULT_MEMORY_MCP_URL = 'http://rm-mcp-memory:3200/mcp'
MCP_TIMEOUT_S = 10.0


class CountedOwner(BaseModel):
    owner_user_id: str
    count: int


class BankStats(BaseModel):
    """Per-bank telemetry sourced from Hindsight.

    `document_count` is from /documents iteration (retain-call volume).
    `fact_count` is the upstream-authoritative LLM-extracted unit count
    from /v1/default/banks; null when the bank doesn't exist upstream
    or when listBanks() failed.
    """

    bank_id: str
    document_count: int
    fact_count: int | None = None
    last_document_at: str | None = None
    by_owner: list[CountedOwner] = Field(default_factory=list)
    by_type: dict[str, int] = Field(default_factory=dict)
    truncated: bool = False


class BopaSessionsBlock(BaseModel):
    total: int
    active: int


class AdoptionStats(BaseModel):
    """Mirror of GetAdoptionStatsOutput in
    Ruimtemeesters-MCP-Servers/packages/memory/src/tools/getAdoptionStats.ts.

    Post-Hindsight-cutover (Memory #67, #70): per-bank shape. The legacy
    `entries.*` and `session_events.*` blocks are gone — `memory.entries`
    is stale post-cutover, and tool-call audit moved to observability
    sidecars (Langfuse / OpenLLMetry) per ADR-0012 §E.5.
    """

    measured_at: str
    banks: list[BankStats] = Field(default_factory=list)
    bopa_sessions: BopaSessionsBlock
    projects: int
    users: int


def _resolve_admin_token() -> str:
    token = (os.environ.get('MEMORY_ADMIN_TOKEN') or '').strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                'MEMORY_ADMIN_TOKEN not configured — the admin memory stats '
                'endpoint is offline until an operator sets it.'
            ),
        )
    return token


def _resolve_mcp_url() -> str:
    return (os.environ.get('RM_MEMORY_MCP_URL') or DEFAULT_MEMORY_MCP_URL).strip() or DEFAULT_MEMORY_MCP_URL


async def _call_get_adoption_stats() -> dict[str, Any]:
    """Issue the admin tools/call to the memory MCP and return the parsed
    payload. Raises HTTPException on transport / protocol failures."""
    rpc_payload = {
        'jsonrpc': '2.0',
        'id': str(uuid.uuid4()),
        'method': 'tools/call',
        'params': {
            'name': 'get_adoption_stats',
            'arguments': {},
        },
    }
    headers = {
        'Authorization': f'Bearer {_resolve_admin_token()}',
        'Accept': 'application/json, text/event-stream',
        'Content-Type': 'application/json',
    }
    url = _resolve_mcp_url()

    try:
        async with httpx.AsyncClient(timeout=MCP_TIMEOUT_S) as client:
            resp = await client.post(url, json=rpc_payload, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        log.warning('memory MCP returned %s for get_adoption_stats', e.response.status_code if e.response else '?')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Memory MCP returned an error: {e}',
        ) from e
    except httpx.HTTPError as e:
        log.warning('memory MCP transport error for get_adoption_stats: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Memory MCP unreachable: {e}',
        ) from e

    try:
        envelope = parse_mcp_response(resp.text)
        return extract_tool_result(envelope)
    except ValueError as e:
        log.warning('memory MCP returned malformed response: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Memory MCP returned a malformed response: {e}',
        ) from e


@router.get('/stats', response_model=AdoptionStats)
async def get_adoption_stats_endpoint(
    user=Depends(get_admin_user),
) -> AdoptionStats:
    """Return cross-user memory adoption stats. Admin only.

    Post-cutover (Memory #67) there's no per-day window — counts are
    per-bank from the live Hindsight state, not from a rolling
    session_events table. The legacy `since_days` query param was
    removed in MCP-Servers #122.
    """
    payload = await _call_get_adoption_stats()
    # Schema-validate inside the same 502 boundary as the MCP transport
    # — a malformed payload from the MCP is a gateway-level fault, not
    # a bug in the chatbot, so it must not surface as 500.
    try:
        return AdoptionStats.model_validate(payload)
    except ValidationError as e:
        log.warning('memory MCP returned a payload that failed schema validation: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Memory MCP returned an unexpected payload shape: {e}',
        ) from e
