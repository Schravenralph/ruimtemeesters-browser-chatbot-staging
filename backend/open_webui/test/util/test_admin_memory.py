"""Unit tests for backend/open_webui/routers/admin_memory.py.

Pure unit tests — no FastAPI test client, no DB. We exercise the
`_call_get_adoption_stats` helper directly and mock `httpx.AsyncClient`
so neither the real client nor the network is touched. The Pydantic
response shape is validated by parsing the result through `AdoptionStats`.

Run with:
    pytest backend/open_webui/test/util/test_admin_memory.py -v
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from open_webui.routers.admin_memory import (
    AdoptionStats,
    _call_get_adoption_stats,
    _resolve_admin_token,
)


SAMPLE_OUTPUT = {
    'measured_at': '2026-05-06T08:00:00.000Z',
    'banks': [
        {
            'bank_id': 'org-ruimtemeesters',
            'document_count': 12,
            'fact_count': 13,
            'last_document_at': '2026-05-22T21:51:14Z',
            'by_owner': [
                {'owner_user_id': 'clerk:ralph', 'count': 8},
                {'owner_user_id': 'clerk:other', 'count': 4},
            ],
            'by_type': {'feedback': 7, 'project': 5},
            'truncated': False,
        },
        {
            'bank_id': 'process-specs',
            'document_count': 42,
            'fact_count': 114,
            'last_document_at': '2026-05-21T22:58:21Z',
            'by_owner': [{'owner_user_id': 'system:admin', 'count': 42}],
            'by_type': {'reference': 42},
            'truncated': False,
        },
    ],
    'bopa_sessions': {'total': 4, 'active': 2},
    'projects': 3,
    'users': 6,
}


def _sse_response(payload: dict, *, framing: str = 'sse') -> MagicMock:
    """Build a MagicMock that mimics httpx.Response wrapping a JSON-RPC
    success envelope around `payload`."""
    inner = json.dumps(payload)
    envelope = {
        'jsonrpc': '2.0',
        'id': 'rpc-id',
        'result': {'content': [{'type': 'text', 'text': inner}]},
    }
    body = json.dumps(envelope) if framing == 'json' else f'event: message\ndata: {json.dumps(envelope)}\n'
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = body
    return resp


def _patch_async_client(response: MagicMock | None = None, *, post_side_effect=None):
    post_mock = AsyncMock()
    if post_side_effect is not None:
        post_mock.side_effect = post_side_effect
    elif response is not None:
        post_mock.return_value = response

    client_instance = MagicMock()
    client_instance.post = post_mock
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    client_instance.__aexit__ = AsyncMock(return_value=None)
    return (
        patch('open_webui.routers.admin_memory.httpx.AsyncClient', MagicMock(return_value=client_instance)),
        post_mock,
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- token resolution ------------------------------------------------------


def test_missing_admin_token_returns_503(monkeypatch):
    monkeypatch.delenv('MEMORY_ADMIN_TOKEN', raising=False)
    with pytest.raises(HTTPException) as exc:
        _resolve_admin_token()
    assert exc.value.status_code == 503
    assert 'MEMORY_ADMIN_TOKEN' in exc.value.detail


def test_blank_admin_token_returns_503(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', '   ')
    with pytest.raises(HTTPException) as exc:
        _resolve_admin_token()
    assert exc.value.status_code == 503


def test_present_admin_token_resolves(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    assert _resolve_admin_token() == 'sekret'


# --- happy path ------------------------------------------------------------


def test_happy_path_returns_typed_payload(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    monkeypatch.setenv('RM_MEMORY_MCP_URL', 'http://test-memory:3200/mcp')

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_OUTPUT))
    with patcher:
        payload = _run(_call_get_adoption_stats())

    typed = AdoptionStats.model_validate(payload)
    assert len(typed.banks) == 2
    org_bank = next(b for b in typed.banks if b.bank_id == 'org-ruimtemeesters')
    assert org_bank.document_count == 12
    assert org_bank.fact_count == 13
    assert org_bank.by_type == {'feedback': 7, 'project': 5}
    assert typed.bopa_sessions.active == 2
    assert typed.projects == 3
    assert typed.users == 6

    # Outbound RPC envelope assertions.
    call = post_mock.call_args
    assert call.args[0] == 'http://test-memory:3200/mcp'
    body = call.kwargs['json']
    assert body['method'] == 'tools/call'
    assert body['params']['name'] == 'get_adoption_stats'
    # Post-cutover: no arguments. since_days was removed in MCP-Servers #122.
    assert body['params']['arguments'] == {}

    headers = call.kwargs['headers']
    assert headers['Authorization'] == 'Bearer sekret'
    assert 'X-Forwarded-User' not in headers, (
        'Admin endpoint must not impersonate a user — see identity.ts buildAdminIdentity (system:admin).'
    )
    assert 'application/json' in headers['Accept']
    assert 'text/event-stream' in headers['Accept']


def test_pure_json_framing_also_parses(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    patcher, _ = _patch_async_client(_sse_response(SAMPLE_OUTPUT, framing='json'))
    with patcher:
        payload = _run(_call_get_adoption_stats())
    assert payload['banks'][0]['document_count'] == 12
    assert payload['banks'][0]['fact_count'] == 13


def test_fact_count_null_when_upstream_missing(monkeypatch):
    """Banks that exist in our SHARED_BANK_IDS but not in Hindsight yet
    return fact_count: null. The BFF must accept that shape (don't reject
    a missing/None field — model_validate has fact_count optional)."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    payload = {
        **SAMPLE_OUTPUT,
        'banks': [
            {
                'bank_id': 'gemeente-knowledge',
                'document_count': 0,
                'fact_count': None,
                'last_document_at': None,
                'by_owner': [],
                'by_type': {},
                'truncated': False,
            },
        ],
    }
    patcher, _ = _patch_async_client(_sse_response(payload))
    with patcher:
        out = _run(_call_get_adoption_stats())
    typed = AdoptionStats.model_validate(out)
    assert typed.banks[0].fact_count is None


# --- failure modes ---------------------------------------------------------


def test_mcp_502_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    failing = MagicMock()
    failing.raise_for_status.side_effect = httpx.HTTPStatusError(
        '502 Bad Gateway', request=MagicMock(), response=MagicMock(status_code=502)
    )
    patcher, _ = _patch_async_client(failing)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502


def test_mcp_timeout_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    patcher, _ = _patch_async_client(post_side_effect=httpx.TimeoutException('timed out'))
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502


def test_malformed_response_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = 'event: ping\ndata: not-json\n\n'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502
    assert 'malformed' in exc.value.detail.lower()


def test_mcp_error_envelope_propagates_as_502(monkeypatch):
    """When the MCP returns a JSON-RPC error envelope (instead of result),
    surface it as a 502 with the message — the chatbot UI can render it."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    err_envelope = {
        'jsonrpc': '2.0',
        'id': 'x',
        'error': {'code': -32603, 'message': 'Forbidden: not admin'},
    }
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = f'event: message\ndata: {json.dumps(err_envelope)}\n'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502
    assert 'forbidden' in exc.value.detail.lower()


def test_string_error_envelope_propagates_as_502(monkeypatch):
    """Bugbot finding (low) on PR #56: a JSON-RPC envelope whose `error`
    field is a bare string (non-conforming server) used to AttributeError
    out of extract_tool_result → 500. Now tolerated as 502 with the
    string used directly as the message."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    err_envelope = {
        'jsonrpc': '2.0',
        'id': 'x',
        'error': 'forbidden — non-dict shape',
    }
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = f'event: message\ndata: {json.dumps(err_envelope)}\n'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502
    assert 'forbidden' in exc.value.detail.lower()


def test_non_object_json_body_propagates_as_502(monkeypatch):
    """Bugbot finding (low) on PR #56: a JSON body that is a bare array
    or `null` would slip past the brace-prefix shortcut and crash
    extract_tool_result with AttributeError → 500. Must surface as 502."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = '[]'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(_call_get_adoption_stats())
    assert exc.value.status_code == 502


def test_late_notification_does_not_clobber_result(monkeypatch):
    """Bugbot finding on PR #56: a JSON-RPC notification arriving after
    the response must NOT overwrite the response payload. The parser
    prefers the envelope with `result`/`error` over later notifications."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')
    response_envelope = {
        'jsonrpc': '2.0',
        'id': 'rpc-id',
        'result': {'content': [{'type': 'text', 'text': json.dumps(SAMPLE_OUTPUT)}]},
    }
    notification_envelope = {
        'jsonrpc': '2.0',
        'method': 'progress',
        'params': {'phase': 'cleanup'},
    }
    body = (
        f'event: message\ndata: {json.dumps(response_envelope)}\n\n'
        f'event: message\ndata: {json.dumps(notification_envelope)}\n'
    )
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = body

    patcher, _ = _patch_async_client(resp)
    with patcher:
        payload = _run(_call_get_adoption_stats())
    # The result envelope wins over the trailing notification.
    assert payload['banks'][0]['document_count'] == 12


def test_validation_error_propagates_as_502(monkeypatch):
    """Bugbot finding on PR #56: when the MCP returns a tool payload
    that doesn't match GetAdoptionStatsOutput, the endpoint must surface
    a 502 (gateway-level fault), not let the Pydantic ValidationError
    leak as a 500."""
    monkeypatch.setenv('MEMORY_ADMIN_TOKEN', 'sekret')

    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415
    from open_webui.utils.auth import get_admin_user

    bad_payload = {'measured_at': 'x', 'entries': {'total': 0}}
    patcher, _ = _patch_async_client(_sse_response(bad_payload))

    # Bypass the auth dep so this stays a unit-style test (no DB).
    app.dependency_overrides[get_admin_user] = lambda: type('U', (), {'id': 'admin', 'email': 'a@x'})()
    try:
        with patcher:
            client = TestClient(app)
            res = client.get('/api/v1/admin/memory/stats')
        assert res.status_code == 502, f'expected 502, got {res.status_code}: {res.text}'
        assert 'unexpected payload shape' in res.text.lower()
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
