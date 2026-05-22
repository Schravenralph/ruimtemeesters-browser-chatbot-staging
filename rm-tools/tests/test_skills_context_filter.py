"""Unit tests for rm-tools/filters/skills_context.py.

Run with:
    pytest rm-tools/tests/test_skills_context_filter.py -v

The rm-skills HTTP service is patched at the `httpx.AsyncClient`
constructor so neither the real client nor the network is touched.
Tests cover persona resolution, mandatory-only filtering, append-not-
replace injection, fail-open behaviour, and per-(persona, user) caching.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Make the filters package importable without requiring an editable install.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filters.skills_context import (  # noqa: E402
    Filter,
    _resolve_persona,
)

# --- helpers --------------------------------------------------------------


def _list_response(skills: list[dict]) -> MagicMock:
    """Mock httpx response for GET /api/v1/skills?persona=... — returns
    a `{skills: [...]}` envelope (matches the rm-skills HTTP shape)."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps({'skills': skills})
    resp.json = MagicMock(return_value={'skills': skills})
    return resp


def _body_response(name: str, body: str, persona: str = 'ro-assistent', mandatory: bool = True) -> MagicMock:
    """Mock httpx response for GET /api/v1/skills/:name — returns the
    skill body and metadata."""
    payload = {
        'name': name,
        'persona': persona,
        'mandatory': mandatory,
        'skill_md': body,
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(payload)
    resp.json = MagicMock(return_value=payload)
    return resp


def _patch_async_client(get_side_effect):
    """Patch httpx.AsyncClient so `async with httpx.AsyncClient() as c:
    await c.get(...)` returns the queued mocks. `get_side_effect` is a
    callable (url, **kwargs) -> MagicMock or a list of MagicMocks to
    consume in order. Returns the patcher and the AsyncMock for client.get."""
    get_mock = AsyncMock()
    if callable(get_side_effect):
        get_mock.side_effect = get_side_effect
    else:
        get_mock.side_effect = list(get_side_effect)

    client_instance = MagicMock()
    client_instance.get = get_mock
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    client_instance.__aexit__ = AsyncMock(return_value=None)

    constructor = MagicMock(return_value=client_instance)
    return patch('filters.skills_context.httpx.AsyncClient', constructor), get_mock


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_body(model_id: str = 'ro-assistent') -> dict:
    return {
        'model': model_id,
        'messages': [
            {'role': 'system', 'content': 'Je bent de RO Assistent.'},
            {'role': 'user', 'content': 'beleidsscan voor Utrecht'},
        ],
    }


def _make_skills_responder(skills_list: list[dict], bodies: dict[str, MagicMock]):
    """Return a side-effect callable that responds to:
    GET .../api/v1/skills?persona=X  -> list response
    GET .../api/v1/skills/<name>     -> bodies[name]
    """

    async def _responder(url, **kwargs):
        if '/api/v1/skills/' in url and not url.rstrip('/').endswith('/api/v1/skills'):
            # Body fetch — pull the trailing name.
            name = url.rsplit('/', 1)[-1]
            return bodies[name]
        return _list_response(skills_list)

    return _responder


# --- persona resolution --------------------------------------------------


def test_resolve_persona_strips_rm_prefix():
    assert _resolve_persona('rm-ro-assistent', None) == 'ro-assistent'


def test_resolve_persona_lowercases_legacy_capitalised_id():
    assert _resolve_persona('RO-Assistent', None) == 'ro-assistent'
    assert _resolve_persona('Juridisch-Assistent', None) == 'juridisch-assistent'
    assert _resolve_persona('Commercieel-Assistent', None) == 'commercieel-assistent'


def test_resolve_persona_from_bare_id():
    assert _resolve_persona('ro-assistent', None) == 'ro-assistent'


def test_resolve_persona_from_metadata_meta_persona():
    metadata = {'model': {'info': {'meta': {'persona': 'juridisch-assistent'}}}}
    # Metadata override beats body model id when present.
    assert _resolve_persona('rm-assistent', metadata) == 'juridisch-assistent'


def test_resolve_persona_returns_empty_for_unrelated_model():
    # Unknown models drop through to empty so the filter no-ops cleanly.
    assert _resolve_persona('', None) == ''


# --- mandatory-only filtering --------------------------------------------


def test_only_mandatory_skills_injected():
    """Skills list contains a mix of mandatory + non-mandatory; only the
    mandatory entry's body is fetched and injected."""
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [
        {'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'},
        {'name': 'casual', 'mandatory': False, 'persona': 'ro-assistent'},
    ]
    bodies = {
        'beleidsscan': _body_response('beleidsscan', 'BELEIDSSCAN_BODY', mandatory=True),
    }
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    sys_msg = body['messages'][0]['content']
    assert 'BELEIDSSCAN_BODY' in sys_msg
    assert '<skill name="beleidsscan"' in sys_msg
    # Two HTTP calls (list + one body), not three.
    assert get_mock.call_count == 2


def test_no_mandatory_skills_is_a_noop():
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [
        {'name': 'optional-one', 'mandatory': False, 'persona': 'ro-assistent'},
    ]
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, {}))
    original = _make_body('ro-assistent')
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    assert body['messages'][0]['content'] == original['messages'][0]['content']
    # Only the list endpoint was hit — no per-skill body fetch.
    assert get_mock.call_count == 1


# --- injection appends, doesn't replace ----------------------------------


def test_injection_appends_to_existing_system_message():
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'BODY_X')}
    patcher, _g = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    sys_msg = body['messages'][0]['content']
    # Pre-existing content preserved.
    assert sys_msg.startswith('Je bent de RO Assistent.')
    # Skill block appended.
    assert '<skills>' in sys_msg
    assert '<skill name="beleidsscan"' in sys_msg
    assert 'BODY_X' in sys_msg


def test_injection_inserts_system_when_none_present():
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'BODY_Y')}
    patcher, _g = _patch_async_client(_make_skills_responder(skills_list, bodies))
    body_no_system = {
        'model': 'ro-assistent',
        'messages': [{'role': 'user', 'content': 'hi'}],
    }
    with patcher:
        body = _run(
            f.inlet(
                body_no_system,
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    assert body['messages'][0]['role'] == 'system'
    assert 'BODY_Y' in body['messages'][0]['content']
    assert body['messages'][1]['role'] == 'user'


# --- fail-open paths ------------------------------------------------------


def test_list_endpoint_500_returns_body_unchanged():
    f = Filter()
    f.valves.cache_ttl_s = 0
    failing = MagicMock()
    failing.raise_for_status.side_effect = httpx.HTTPStatusError(
        '500 Internal Server Error', request=MagicMock(), response=MagicMock()
    )
    patcher, _g = _patch_async_client(lambda url, **kw: failing)
    with patcher:
        # Wrap in async wrapper since side_effect callable must be awaitable.
        pass
    # Real check: the side_effect needs an async function returning the failing
    # response. Refactor:

    async def _responder(url, **kw):
        return failing

    original = _make_body('ro-assistent')
    patcher2, _g2 = _patch_async_client(_responder)
    with patcher2:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    assert body['messages'][0]['content'] == original['messages'][0]['content']


def test_timeout_returns_body_unchanged():
    f = Filter()
    f.valves.cache_ttl_s = 0
    original = _make_body('ro-assistent')

    async def _responder(url, **kw):
        raise httpx.TimeoutException('timed out')

    patcher, _g = _patch_async_client(_responder)
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    assert body['messages'][0]['content'] == original['messages'][0]['content']


def test_connection_refused_returns_body_unchanged():
    f = Filter()
    f.valves.cache_ttl_s = 0
    original = _make_body('ro-assistent')

    async def _responder(url, **kw):
        raise httpx.ConnectError('connection refused')

    patcher, _g = _patch_async_client(_responder)
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    assert body['messages'][0]['content'] == original['messages'][0]['content']


def test_body_fetch_failure_skips_just_that_skill():
    """If the list call succeeds but a single body fetch 500s, the filter
    must continue with whatever bodies did come back — not nuke the whole
    injection. Here only the failing skill is mandatory; injection ends
    up a no-op but the chat still proceeds."""
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    failing_body = MagicMock()
    failing_body.raise_for_status.side_effect = httpx.HTTPStatusError('500', request=MagicMock(), response=MagicMock())

    async def _responder(url, **kw):
        if url.rstrip('/').endswith('/api/v1/skills/beleidsscan'):
            return failing_body
        return _list_response(skills_list)

    original = _make_body('ro-assistent')
    patcher, _g = _patch_async_client(_responder)
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    # No <skills> block injected.
    assert body['messages'][0]['content'] == original['messages'][0]['content']


# --- cache ---------------------------------------------------------------


def test_cache_avoids_second_rpc_within_ttl():
    """Two successive inlets for the same (persona, user) within
    cache_ttl_s should hit the rm-skills service exactly once for the
    list endpoint, once per skill body."""
    f = Filter()
    f.valves.cache_ttl_s = 60
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'CACHED_BODY')}
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        b1 = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
        b2 = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    # First call: list + body = 2 GETs. Second call: cache hit = 0 GETs.
    assert get_mock.call_count == 2
    assert 'CACHED_BODY' in b1['messages'][0]['content']
    assert 'CACHED_BODY' in b2['messages'][0]['content']


def test_cache_key_isolates_per_user():
    """User A and user B both prime within TTL — each should trigger
    independent fetches (cache keyed on (persona, user_id))."""
    f = Filter()
    f.valves.cache_ttl_s = 60
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'BODY_Z')}
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'user-a', 'email': 'a@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
        _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'user-b', 'email': 'b@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    # Two users → 2 list + 2 body fetches = 4 GETs.
    assert get_mock.call_count == 4


# --- model scoping --------------------------------------------------------


def test_off_target_model_skips_injection():
    """Filter must no-op on models outside the target_models valve."""
    f = Filter()
    f.valves.cache_ttl_s = 0
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'BODY_Q')}
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        body = _run(
            f.inlet(
                _make_body('rm-demografie-analist'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'rm-demografie-analist'},
            )
        )
    get_mock.assert_not_called()
    assert '<skill' not in body['messages'][0]['content']


def test_master_kill_switch_disables_filter():
    f = Filter()
    f.valves.enabled = False
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    bodies = {'beleidsscan': _body_response('beleidsscan', 'BODY_K')}
    patcher, get_mock = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    get_mock.assert_not_called()
    assert '<skill' not in body['messages'][0]['content']


def test_max_skill_chars_truncates_body():
    """Bodies larger than max_skill_chars get truncated to that length so
    a runaway markdown file can't tank the prompt budget."""
    f = Filter()
    f.valves.cache_ttl_s = 0
    f.valves.max_skill_chars = 20
    skills_list = [{'name': 'beleidsscan', 'mandatory': True, 'persona': 'ro-assistent'}]
    long_body = 'A' * 500
    bodies = {'beleidsscan': _body_response('beleidsscan', long_body)}
    patcher, _g = _patch_async_client(_make_skills_responder(skills_list, bodies))
    with patcher:
        body = _run(
            f.inlet(
                _make_body('ro-assistent'),
                __user__={'id': 'me', 'email': 'me@example.org'},
                __metadata__={'model_id': 'ro-assistent'},
            )
        )
    sys_msg = body['messages'][0]['content']
    # The skill block contains at most max_skill_chars of body content,
    # but the wrapping XML adds extra chars — assert the truncation
    # marker is present and the full 500-char run is not.
    assert 'AAAAAAAAAAAAAAAAAAAA' in sys_msg  # 20 A's = the cap
    assert 'A' * 500 not in sys_msg


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
