"""User-facing BFF for the Ruimtemeesters memory MCP.

Surfaces the MCP's read + write tools (list / get / save / forget)
over HTTP so the chatbot frontend can render a memory panel without
direct MCP access. Every request runs under the calling user's
identity: the chatbot forwards `user.email` as `X-Forwarded-User`
and authenticates to the MCP with the gateway token. The MCP applies
its own scope predicates server-side (Session 1 read predicate +
saveMemory upsert key + forgetMemory ambiguity guard), so the BFF
stays a pass-through.

Distinct from `admin_memory.py`:
- Auth: gateway token (not admin token).
- Identity: the caller's email is forwarded; no synthetic admin
  identity.
- Gate: `get_verified_user` (any signed-in user).
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, ValidationError, model_validator

from open_webui.utils.auth import get_verified_user
from open_webui.utils.mcp_response import extract_tool_result, parse_mcp_response

log = logging.getLogger(__name__)

router = APIRouter()


DEFAULT_MEMORY_MCP_URL = 'http://rm-mcp-memory:3200/mcp'
MCP_TIMEOUT_S = 10.0

MEMORY_TYPE = Literal['user', 'feedback', 'project', 'reference', 'session-summary']
SCOPE = Literal['user', 'project', 'global']


# --- Pydantic models -------------------------------------------------------


class MemoryEntry(BaseModel):
    """Mirror of IndexEntry in
    Ruimtemeesters-MCP-Servers/packages/memory/src/tools/listMemories.ts."""

    name: str
    type: str
    scope: str
    description: str
    owner_user_id: str
    project_id: str | None = None
    updated_at: str


class ListMemoriesOutput(BaseModel):
    entries: list[MemoryEntry] = Field(default_factory=list)


class GetMemoryOutput(BaseModel):
    """Mirror of GetMemoryOutput in
    Ruimtemeesters-MCP-Servers/packages/memory/src/tools/getMemory.ts."""

    id: str
    name: str
    type: str
    scope: str
    description: str
    content: str
    owner_user_id: str
    project_id: str | None = None
    created_at: str
    updated_at: str


class SaveMemoryRequest(BaseModel):
    """Body for POST /api/v1/rm-memory. Mirror of saveMemoryTool's
    input schema in Ruimtemeesters-MCP-Servers (incl. the
    `scope='project' ↔ project_id` invariant)."""

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=200)
    type: MEMORY_TYPE
    content: str = Field(min_length=1, max_length=65536)
    scope: SCOPE | None = None
    project_id: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode='after')
    def _check_project_id_scope_invariant(self) -> 'SaveMemoryRequest':
        if self.scope == 'project' and not self.project_id:
            raise ValueError("project_id is required when scope='project'")
        if self.scope != 'project' and self.project_id is not None:
            raise ValueError("project_id must be omitted unless scope='project'")
        return self


class SaveMemoryOutput(BaseModel):
    id: str
    name: str
    type: str
    scope: str
    project_id: str | None = None
    created: bool
    updated: bool


class ForgetMemoryOutput(BaseModel):
    deleted: bool
    rows: int


class ActiveProject(BaseModel):
    """Mirror of getActiveProject's row shape in
    Ruimtemeesters-Memory/src/services/getActiveProject.ts."""

    project_id: str
    kind: str
    label: str | None = None
    set_at: str


# --- helpers ---------------------------------------------------------------


def _resolve_gateway_token() -> str:
    token = (os.environ.get('MEMORY_GATEWAY_TOKEN') or '').strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=('MEMORY_GATEWAY_TOKEN not configured — the rm-memory BFF is offline until an operator sets it.'),
        )
    return token


def _resolve_mcp_url() -> str:
    return (os.environ.get('RM_MEMORY_MCP_URL') or DEFAULT_MEMORY_MCP_URL).strip() or DEFAULT_MEMORY_MCP_URL


async def _call_user_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    user_email: str | None,
    x_thread_id: str | None = None,
) -> dict[str, Any]:
    """Issue a user-scoped tools/call to the memory MCP and return the
    parsed payload. Shared transport for all rm-memory endpoints.

    When ``x_thread_id`` is provided, it is forwarded as ``X-Thread-Id``
    so the memory service can scope (user, chat) keyed state — e.g.
    active-project lookups. The header is omitted otherwise to avoid
    inflating requests that don't need it.

    Raises HTTPException on transport / parser / error-envelope failures
    (always 502 / 503), preserving the upstream message when available.
    """
    rpc_payload = {
        'jsonrpc': '2.0',
        'id': str(uuid.uuid4()),
        'method': 'tools/call',
        'params': {
            'name': tool_name,
            'arguments': arguments,
        },
    }
    headers = {
        'Authorization': f'Bearer {_resolve_gateway_token()}',
        'Accept': 'application/json, text/event-stream',
        'Content-Type': 'application/json',
    }
    if user_email:
        headers['X-Forwarded-User'] = user_email
    if x_thread_id:
        headers['X-Thread-Id'] = x_thread_id

    url = _resolve_mcp_url()

    try:
        async with httpx.AsyncClient(timeout=MCP_TIMEOUT_S) as client:
            resp = await client.post(url, json=rpc_payload, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Preserve the upstream body in the detail so a 401 from the MCP
        # surfaces with its real message instead of the bare httpx repr.
        # Body length is capped to keep the chatbot response small.
        upstream = ''
        if e.response is not None:
            try:
                upstream = (e.response.text or '')[:500]
            except Exception:  # noqa: BLE001 — defensive read
                upstream = ''
        log.warning(
            'rm-memory MCP returned %s for %s',
            e.response.status_code if e.response else '?',
            tool_name,
        )
        suffix = f' — {upstream}' if upstream else ''
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-memory MCP returned an error: {e}{suffix}',
        ) from e
    except httpx.HTTPError as e:
        log.warning('rm-memory MCP transport error for %s: %s', tool_name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-memory MCP unreachable: {e}',
        ) from e

    try:
        envelope = parse_mcp_response(resp.text)
        return extract_tool_result(envelope)
    except ValueError as e:
        log.warning('rm-memory MCP returned malformed response for %s: %s', tool_name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-memory MCP returned a malformed response: {e}',
        ) from e


def _validate_or_502(model: type[BaseModel], payload: dict[str, Any], tool_name: str) -> Any:
    """Schema-validate the MCP payload inside a 502 boundary. A malformed
    response is a gateway-level fault, never a 500 from this app."""
    try:
        return model.model_validate(payload)
    except ValidationError as e:
        log.warning(
            'rm-memory MCP %s returned a payload that failed schema validation: %s',
            tool_name,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-memory MCP returned an unexpected payload shape: {e}',
        ) from e


def _user_email(user: Any) -> str | None:
    return getattr(user, 'email', None) or None


# --- endpoints -------------------------------------------------------------


@router.get('', response_model=ListMemoriesOutput)
async def list_memories_endpoint(
    scope: SCOPE | None = Query(default=None, description='Restrict to one scope.'),
    project_id: str | None = Query(
        default=None,
        max_length=256,
        description='When given, project entries match this project id.',
    ),
    type: MEMORY_TYPE | None = Query(
        default=None,
        description='Restrict to one memory type.',
        alias='type',
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=200,
        description='Up to 200; default 100 on the MCP side.',
    ),
    user=Depends(get_verified_user),
) -> ListMemoriesOutput:
    """List the calling user's memory entries (user own + global + project).

    Returns the index view: name + description + metadata, no content.
    Use a follow-up `GET /{name}` call to retrieve content.

    Mounted at the collection root (no `/list` segment) so `name == 'list'`
    can't shadow this route — Bugbot finding on PR #61.
    """
    arguments: dict[str, Any] = {}
    if scope is not None:
        arguments['scope'] = scope
    if project_id is not None:
        arguments['project_id'] = project_id
    if type is not None:
        arguments['type'] = type
    if limit is not None:
        arguments['limit'] = limit

    payload = await _call_user_tool(
        tool_name='list_memories',
        arguments=arguments,
        user_email=_user_email(user),
    )
    return _validate_or_502(ListMemoriesOutput, payload, 'list_memories')


@router.get('/active-project', response_model=ActiveProject | None)
async def get_active_project_endpoint(
    chat_id: str = Query(
        ...,
        min_length=1,
        max_length=128,
        description='The chat / thread id the caller is asking about. Forwarded as X-Thread-Id to the memory service.',
    ),
    user=Depends(get_verified_user),
) -> ActiveProject | None:
    """Return the active project bound to (user, chat), or `null` when
    nothing is bound. The memory service keys the row on `X-Thread-Id`
    + the forwarded user, so a chat that hasn't yet called
    `set_active_project` simply returns null.

    Mounted before `/{name}` so a memory entry named "active-project"
    can't shadow this route — same pattern as the `name == 'list'`
    bugbot finding on #61.
    """
    payload = await _call_user_tool(
        tool_name='get_active_project',
        arguments={},
        user_email=_user_email(user),
        x_thread_id=chat_id,
    )
    # MCP can legitimately return null. Handle the empty/null case
    # explicitly before validating — `_validate_or_502` would 502 on a
    # None payload.
    if payload is None or payload == {} or payload == {'active_project': None}:
        return None
    # Some MCP shapes wrap the row under an `active_project` key; others
    # return the row directly. Normalise here so downstream stays simple.
    row = payload.get('active_project') if isinstance(payload, dict) and 'active_project' in payload else payload
    if row is None:
        return None
    return _validate_or_502(ActiveProject, row, 'get_active_project')


@router.get('/{name}', response_model=GetMemoryOutput)
async def get_memory_endpoint(
    name: str = Path(..., min_length=1, max_length=120),
    type: MEMORY_TYPE | None = Query(default=None, alias='type'),
    project_id: str | None = Query(default=None, max_length=256),
    user=Depends(get_verified_user),
) -> GetMemoryOutput:
    """Fetch one memory entry's full content. Read predicate is the same
    Session 1 cone as `/list`."""
    arguments: dict[str, Any] = {'name': name}
    if type is not None:
        arguments['type'] = type
    if project_id is not None:
        arguments['project_id'] = project_id

    payload = await _call_user_tool(
        tool_name='get_memory',
        arguments=arguments,
        user_email=_user_email(user),
    )
    return _validate_or_502(GetMemoryOutput, payload, 'get_memory')


@router.post('', response_model=SaveMemoryOutput)
async def save_memory_endpoint(
    body: SaveMemoryRequest = Body(...),
    user=Depends(get_verified_user),
) -> SaveMemoryOutput:
    """Upsert a memory entry. Re-saving with the same (scope, project,
    type, name) overwrites; new tuples insert."""
    arguments: dict[str, Any] = {
        'name': body.name,
        'description': body.description,
        'type': body.type,
        'content': body.content,
    }
    if body.scope is not None:
        arguments['scope'] = body.scope
    if body.project_id is not None:
        arguments['project_id'] = body.project_id

    payload = await _call_user_tool(
        tool_name='save_memory',
        arguments=arguments,
        user_email=_user_email(user),
    )
    return _validate_or_502(SaveMemoryOutput, payload, 'save_memory')


@router.delete('/{name}', response_model=ForgetMemoryOutput)
async def forget_memory_endpoint(
    name: str = Path(..., min_length=1, max_length=120),
    type: MEMORY_TYPE | None = Query(default=None, alias='type'),
    scope: SCOPE | None = Query(default=None),
    project_id: str | None = Query(default=None, max_length=256),
    user=Depends(get_verified_user),
) -> ForgetMemoryOutput:
    """Hard-delete one of the caller's memory entries. The MCP returns
    `{deleted: bool, rows: number}`; if `rows == 0` (no match), the BFF
    still surfaces 200 with the result — the panel renders that as "no
    matching entry to forget" rather than 404 because the MCP's read
    predicate may legitimately hide a row another caller can see."""
    arguments: dict[str, Any] = {'name': name}
    if type is not None:
        arguments['type'] = type
    if scope is not None:
        arguments['scope'] = scope
    if project_id is not None:
        arguments['project_id'] = project_id

    payload = await _call_user_tool(
        tool_name='forget_memory',
        arguments=arguments,
        user_email=_user_email(user),
    )
    return _validate_or_502(ForgetMemoryOutput, payload, 'forget_memory')
