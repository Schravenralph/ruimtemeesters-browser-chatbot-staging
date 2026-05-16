"""Unit tests for backend/open_webui/routers/rm_memory.py.

Direct-helper tests exercise `_call_user_tool` and mock httpx.AsyncClient.
Endpoint tests use FastAPI's TestClient with the auth dependency
overridden — no DB, no real network.

Run with:
    pytest backend/open_webui/test/util/test_rm_memory.py -v
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from open_webui.routers.rm_memory import (
    ActiveProject,
    ListMemoriesOutput,
    _call_user_tool,
    _resolve_gateway_token,
)


SAMPLE_LIST = {
    'entries': [
        {
            'name': 'identity',
            'type': 'user',
            'scope': 'user',
            'description': 'sole admin, never use other RM emails',
            'owner_user_id': 'clerk:ralph',
            'project_id': None,
            'updated_at': '2026-05-01T12:00:00.000Z',
        },
        {
            'name': 'project_brief',
            'type': 'project',
            'scope': 'project',
            'description': 'BOPA Markt 1, Den Bosch',
            'owner_user_id': 'clerk:ralph',
            'project_id': '7',
            'updated_at': '2026-05-05T08:00:00.000Z',
        },
    ],
}

SAMPLE_GET = {
    'id': 'uuid-1',
    'name': 'identity',
    'type': 'user',
    'scope': 'user',
    'description': 'sole admin, never use other RM emails',
    'content': 'Ralph is the sole admin; never use other RM emails.',
    'owner_user_id': 'clerk:ralph',
    'project_id': None,
    'created_at': '2026-04-01T00:00:00.000Z',
    'updated_at': '2026-05-01T12:00:00.000Z',
}

SAMPLE_SAVE = {
    'id': 'uuid-1',
    'name': 'identity',
    'type': 'user',
    'scope': 'user',
    'project_id': None,
    'created': False,
    'updated': True,
}

SAMPLE_FORGET = {'deleted': True, 'rows': 1}


def _sse_response(payload: dict, *, framing: str = 'sse') -> MagicMock:
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
        patch(
            'open_webui.routers.rm_memory.httpx.AsyncClient',
            MagicMock(return_value=client_instance),
        ),
        post_mock,
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _override_user(email: str | None = 'ralph@example.org'):
    """Build a (patcher, undo) pair that overrides get_verified_user on
    the FastAPI app for the duration of a test. Used by endpoint-level
    tests that go through TestClient."""
    from open_webui.main import app  # noqa: PLC0415
    from open_webui.utils.auth import get_verified_user  # noqa: PLC0415

    def _fake():
        return type('U', (), {'id': 'u', 'email': email})()

    app.dependency_overrides[get_verified_user] = _fake
    return lambda: app.dependency_overrides.pop(get_verified_user, None)


# --- gateway token ---------------------------------------------------------


def test_missing_gateway_token_returns_503(monkeypatch):
    monkeypatch.delenv('MEMORY_GATEWAY_TOKEN', raising=False)
    with pytest.raises(HTTPException) as exc:
        _resolve_gateway_token()
    assert exc.value.status_code == 503
    assert 'MEMORY_GATEWAY_TOKEN' in exc.value.detail


def test_blank_gateway_token_returns_503(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', '   ')
    with pytest.raises(HTTPException) as exc:
        _resolve_gateway_token()
    assert exc.value.status_code == 503


# --- _call_user_tool happy path -------------------------------------------


def test_call_user_tool_forwards_email_and_token(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    monkeypatch.setenv('RM_MEMORY_MCP_URL', 'http://test-memory:3200/mcp')

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_LIST))
    with patcher:
        payload = _run(
            _call_user_tool(
                tool_name='list_memories',
                arguments={'scope': 'user'},
                user_email='ralph@example.org',
            )
        )

    assert len(payload['entries']) == 2
    call = post_mock.call_args
    assert call.args[0] == 'http://test-memory:3200/mcp'
    body = call.kwargs['json']
    assert body['method'] == 'tools/call'
    assert body['params']['name'] == 'list_memories'
    assert body['params']['arguments'] == {'scope': 'user'}

    headers = call.kwargs['headers']
    assert headers['Authorization'] == 'Bearer gateway-secret'
    assert headers['X-Forwarded-User'] == 'ralph@example.org'
    assert 'application/json' in headers['Accept']
    assert 'text/event-stream' in headers['Accept']


def test_call_user_tool_omits_x_forwarded_user_when_missing(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_LIST))
    with patcher:
        _run(
            _call_user_tool(
                tool_name='list_memories',
                arguments={},
                user_email=None,
            )
        )
    headers = post_mock.call_args.kwargs['headers']
    assert 'X-Forwarded-User' not in headers


# --- failure modes (shared transport) -------------------------------------


def test_call_user_tool_502_propagates_with_upstream_body(monkeypatch):
    """HTTPStatusError must surface as 502, with the upstream response
    body included in the detail (Bugbot finding on PR #60)."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    failing = MagicMock()
    failing_response = MagicMock(status_code=502)
    failing_response.text = 'Bad Gateway: upstream timeout'
    failing.raise_for_status.side_effect = httpx.HTTPStatusError(
        '502 Bad Gateway', request=MagicMock(), response=failing_response
    )
    patcher, _ = _patch_async_client(failing)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(
                _call_user_tool(
                    tool_name='list_memories',
                    arguments={},
                    user_email='ralph@example.org',
                )
            )
    assert exc.value.status_code == 502
    assert 'Bad Gateway: upstream timeout' in exc.value.detail


def test_call_user_tool_timeout_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    patcher, _ = _patch_async_client(post_side_effect=httpx.TimeoutException('timed out'))
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(
                _call_user_tool(
                    tool_name='list_memories',
                    arguments={},
                    user_email='ralph@example.org',
                )
            )
    assert exc.value.status_code == 502


def test_call_user_tool_malformed_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = 'event: ping\ndata: not-json\n\n'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(
                _call_user_tool(
                    tool_name='list_memories',
                    arguments={},
                    user_email='ralph@example.org',
                )
            )
    assert exc.value.status_code == 502


def test_call_user_tool_error_envelope_propagates_as_502(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    err_envelope = {
        'jsonrpc': '2.0',
        'id': 'x',
        'error': {'code': -32602, 'message': 'Invalid arguments: scope'},
    }
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.text = f'event: message\ndata: {json.dumps(err_envelope)}\n'
    patcher, _ = _patch_async_client(bad)
    with patcher:
        with pytest.raises(HTTPException) as exc:
            _run(
                _call_user_tool(
                    tool_name='list_memories',
                    arguments={},
                    user_email='ralph@example.org',
                )
            )
    assert exc.value.status_code == 502
    assert 'invalid' in exc.value.detail.lower()


# --- /list endpoint (regression on prior cycle) ---------------------------


def test_list_endpoint_passes_args_through(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_LIST))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get(
                '/api/v1/rm-memory',
                params={'scope': 'project', 'project_id': '42', 'type': 'feedback', 'limit': 10},
            )
        assert res.status_code == 200, res.text
        args = post_mock.call_args.kwargs['json']['params']['arguments']
        assert args == {'scope': 'project', 'project_id': '42', 'type': 'feedback', 'limit': 10}
    finally:
        undo()


def test_list_endpoint_validation_error_is_502(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    bad_payload = {'entries': [{'name': 'x'}]}  # missing required type/scope/etc
    patcher, _ = _patch_async_client(_sse_response(bad_payload))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get('/api/v1/rm-memory')
        assert res.status_code == 502, res.text
        assert 'unexpected payload shape' in res.text.lower()
    finally:
        undo()


# --- /{name} GET endpoint --------------------------------------------------


def test_get_endpoint_returns_full_content(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_GET))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get('/api/v1/rm-memory/identity')
        assert res.status_code == 200, res.text
        body = res.json()
        assert body['name'] == 'identity'
        assert body['content'].startswith('Ralph is the sole admin')
        # The MCP RPC name argument matches the path.
        rpc = post_mock.call_args.kwargs['json']
        assert rpc['params']['name'] == 'get_memory'
        assert rpc['params']['arguments']['name'] == 'identity'
    finally:
        undo()


def test_get_endpoint_passes_optional_disambiguators(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_GET))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get(
                '/api/v1/rm-memory/identity',
                params={'type': 'user', 'project_id': '7'},
            )
        assert res.status_code == 200
        args = post_mock.call_args.kwargs['json']['params']['arguments']
        assert args == {'name': 'identity', 'type': 'user', 'project_id': '7'}
    finally:
        undo()


# --- POST endpoint (save) --------------------------------------------------


def test_save_endpoint_happy(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_SAVE))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).post(
                '/api/v1/rm-memory',
                json={
                    'name': 'identity',
                    'description': 'sole admin',
                    'type': 'user',
                    'content': 'Ralph is the sole admin.',
                },
            )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body['name'] == 'identity'
        assert body['updated'] is True
        rpc = post_mock.call_args.kwargs['json']
        assert rpc['params']['name'] == 'save_memory'
        # Optional fields (scope, project_id) NOT fabricated when absent.
        assert 'scope' not in rpc['params']['arguments']
        assert 'project_id' not in rpc['params']['arguments']
    finally:
        undo()


def test_save_rejects_project_scope_without_project_id(monkeypatch):
    """Pydantic invariant: scope='project' requires project_id. Surfaced
    as a 422 client-error before we even contact the MCP."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_SAVE))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).post(
                '/api/v1/rm-memory',
                json={
                    'name': 'x',
                    'description': 'd',
                    'type': 'project',
                    'content': 'c',
                    'scope': 'project',
                    # project_id intentionally missing
                },
            )
        assert res.status_code == 422, res.text
        post_mock.assert_not_called()
    finally:
        undo()


def test_save_rejects_project_id_without_project_scope(monkeypatch):
    """Inverse invariant: project_id is forbidden unless scope='project'."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_SAVE))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).post(
                '/api/v1/rm-memory',
                json={
                    'name': 'x',
                    'description': 'd',
                    'type': 'user',
                    'content': 'c',
                    'scope': 'user',
                    'project_id': 'leaked',
                },
            )
        assert res.status_code == 422, res.text
        post_mock.assert_not_called()
    finally:
        undo()


# --- DELETE endpoint (forget) ----------------------------------------------


def test_forget_endpoint_returns_deleted_rows(monkeypatch):
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_FORGET))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).delete(
                '/api/v1/rm-memory/identity',
                params={'type': 'user', 'scope': 'user'},
            )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body == {'deleted': True, 'rows': 1}
        rpc = post_mock.call_args.kwargs['json']
        assert rpc['params']['name'] == 'forget_memory'
        args = rpc['params']['arguments']
        assert args == {'name': 'identity', 'type': 'user', 'scope': 'user'}
    finally:
        undo()


def test_forget_endpoint_zero_rows_still_200(monkeypatch):
    """If the MCP returns deleted=false / rows=0 (no match), the BFF
    surfaces 200 with the result so the panel can render 'no matching
    entry to forget' rather than a confusing 404."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, _ = _patch_async_client(_sse_response({'deleted': False, 'rows': 0}))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).delete('/api/v1/rm-memory/missing')
        assert res.status_code == 200, res.text
        assert res.json() == {'deleted': False, 'rows': 0}
    finally:
        undo()


# --- /active-project GET endpoint ------------------------------------------


SAMPLE_ACTIVE_PROJECT = {
    'project_id': 'beleidsscan:GM0344:energietransitie',
    'kind': 'beleidsscan',
    'label': 'Utrecht — energietransitie',
    'set_at': '2026-05-16T01:30:00Z',
}


def test_call_user_tool_forwards_x_thread_id_when_set(monkeypatch):
    """The optional `x_thread_id` arg must surface as the `X-Thread-Id`
    header so the memory service can scope (user, chat) keyed state."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_ACTIVE_PROJECT))
    with patcher:
        _run(
            _call_user_tool(
                tool_name='get_active_project',
                arguments={},
                user_email='ralph@example.org',
                x_thread_id='chat-abc-123',
            )
        )
    headers = post_mock.call_args.kwargs['headers']
    assert headers['X-Thread-Id'] == 'chat-abc-123'


def test_call_user_tool_omits_x_thread_id_when_missing(monkeypatch):
    """Existing endpoints that don't pass x_thread_id should not see the
    header — keep the request small + backward-compatible."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_LIST))
    with patcher:
        _run(
            _call_user_tool(
                tool_name='list_memories',
                arguments={},
                user_email='ralph@example.org',
            )
        )
    headers = post_mock.call_args.kwargs['headers']
    assert 'X-Thread-Id' not in headers


def test_active_project_endpoint_returns_row(monkeypatch):
    """Happy path: MCP returns the active project row → 200 + typed body."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, post_mock = _patch_async_client(_sse_response(SAMPLE_ACTIVE_PROJECT))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get(
                '/api/v1/rm-memory/active-project',
                params={'chat_id': 'chat-abc-123'},
            )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body['project_id'] == 'beleidsscan:GM0344:energietransitie'
        assert body['kind'] == 'beleidsscan'
        assert body['label'] == 'Utrecht — energietransitie'

        # chat_id arrived as X-Thread-Id; the MCP RPC carries no arguments.
        headers = post_mock.call_args.kwargs['headers']
        assert headers['X-Thread-Id'] == 'chat-abc-123'
        rpc = post_mock.call_args.kwargs['json']
        assert rpc['params']['name'] == 'get_active_project'
        assert rpc['params']['arguments'] == {}
    finally:
        undo()


def test_active_project_endpoint_returns_null_when_no_project(monkeypatch):
    """A chat that hasn't called set_active_project: the MCP returns null;
    the BFF surfaces null (200) so the frontend can render an empty
    pill rather than a confusing 404."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    patcher, _ = _patch_async_client(_sse_response({'active_project': None}))
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get(
                '/api/v1/rm-memory/active-project',
                params={'chat_id': 'cold-chat'},
            )
        assert res.status_code == 200, res.text
        assert res.json() is None
    finally:
        undo()


def test_active_project_endpoint_requires_chat_id(monkeypatch):
    """Missing chat_id ⇒ FastAPI 422 (validation). We never let a chat-less
    request reach the MCP — it has no way to scope without a thread id."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    undo = _override_user()
    try:
        res = TestClient(app).get('/api/v1/rm-memory/active-project')
        assert res.status_code == 422, res.text
    finally:
        undo()


def test_active_project_endpoint_502_propagates(monkeypatch):
    """Transport / upstream failures still 502 like the other endpoints."""
    monkeypatch.setenv('MEMORY_GATEWAY_TOKEN', 'gateway-secret')
    from fastapi.testclient import TestClient

    from open_webui.main import app  # noqa: PLC0415

    failing = MagicMock()
    failing_response = MagicMock(status_code=502)
    failing_response.text = 'upstream offline'
    failing.raise_for_status.side_effect = httpx.HTTPStatusError('502', request=MagicMock(), response=failing_response)
    patcher, _ = _patch_async_client(failing)
    undo = _override_user()
    try:
        with patcher:
            res = TestClient(app).get(
                '/api/v1/rm-memory/active-project',
                params={'chat_id': 'chat-abc-123'},
            )
        assert res.status_code == 502, res.text
        assert 'rm-memory MCP' in res.json()['detail']
    finally:
        undo()


# --- regression: ListMemoriesOutput schema still parses sample fixture -----


def test_list_memories_output_schema_validates():
    typed = ListMemoriesOutput.model_validate(SAMPLE_LIST)
    assert len(typed.entries) == 2
    assert typed.entries[1].project_id == '7'


def test_active_project_schema_validates():
    typed = ActiveProject.model_validate(SAMPLE_ACTIVE_PROJECT)
    assert typed.project_id == 'beleidsscan:GM0344:energietransitie'
    assert typed.kind == 'beleidsscan'
