"""Unit tests for rm-tools/filters/memory_save_prompt.py.

Run with:
    pytest rm-tools/tests/test_memory_save_prompt_filter.py -v

Tests are pure: the filter makes no outbound RPCs, so no patching needed.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filters.memory_save_prompt import (  # noqa: E402
    Filter,
    _approx_tokens,
    _build_instruction,
    _format_count,
)


def _msg(role: str, length: int) -> dict:
    """Build a message of approximately `length` characters of content."""
    return {'role': role, 'content': 'x' * length}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_filter(**valves) -> Filter:
    f = Filter()
    for k, v in valves.items():
        setattr(f.valves, k, v)
    return f


# ----- pure-function tests -----


def test_approx_tokens_empty():
    assert _approx_tokens([]) == 0
    assert _approx_tokens(None) == 0  # type: ignore[arg-type]


def test_approx_tokens_string_content():
    msgs = [_msg('user', 4000), _msg('assistant', 4000)]
    # 8000 chars / 4 = 2000 tokens (rough)
    assert _approx_tokens(msgs) == 2000


def test_approx_tokens_list_content_text_parts():
    msgs = [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'a' * 100},
                {'type': 'image_url', 'image_url': {'url': 'data:...'}},
                {'type': 'text', 'text': 'b' * 200},
            ],
        }
    ]
    # 300 chars / 4 = 75 tokens; image part ignored
    assert _approx_tokens(msgs) == 75


def test_approx_tokens_skips_malformed_messages():
    msgs = [
        _msg('user', 40),
        'not-a-dict',  # type: ignore[list-item]
        {'role': 'assistant'},  # no content
        _msg('assistant', 40),
    ]
    assert _approx_tokens(msgs) == 20  # 80 chars / 4


def test_format_count_dutch_thousands():
    assert _format_count(100000) == '100.000'
    assert _format_count(1_000_000) == '1.000.000'
    assert _format_count(42) == '42'


def test_build_instruction_includes_threshold_and_next():
    block = _build_instruction(100_000, 250_000)
    assert '100.000' in block
    assert '250.000' in block
    assert 'summarize_session' in block
    assert '[Systeem-signaal' in block


def test_build_instruction_no_next_threshold():
    block = _build_instruction(1_000_000, None)
    assert '1.000.000' in block
    # The "ask again at next threshold" tail should be absent.
    assert 'opnieuw rond' not in block


# ----- filter behaviour tests -----


def test_inlet_no_op_below_first_threshold():
    f = _make_filter(thresholds='100000,250000')
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 1000), _msg('user', 4000)],
    }
    original = body['messages'].copy()
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert out['messages'] == original
    assert ('u1', 'c1') not in f._asked


def test_inlet_injects_at_threshold_crossing():
    f = _make_filter(thresholds='1000,5000')
    body = {
        'model': 'rm-assistent',
        # 4040 chars → ~1010 tokens, crosses 1000
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    sys_content = out['messages'][0]['content']
    assert '[Systeem-signaal' in sys_content
    assert '1.000' in sys_content
    assert '5.000' in sys_content  # next threshold mentioned
    assert 1000 in f._asked[('u1', 'c1')]


def test_inlet_does_not_re_inject_for_same_threshold():
    f = _make_filter(thresholds='1000,5000')
    body1 = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    _run(f.inlet(body1, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))

    body2 = {
        'model': 'rm-assistent',
        # Slightly larger but still under 5000-token next threshold
        'messages': [_msg('system', 40), _msg('user', 4400)],
    }
    out = _run(f.inlet(body2, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    # The system message should NOT have been augmented a second time —
    # i.e. only the original 40 chars (no '[Systeem-signaal' appended).
    assert '[Systeem-signaal' not in out['messages'][0]['content']


def test_inlet_re_injects_when_crossing_next_threshold():
    f = _make_filter(thresholds='1000,5000')
    body1 = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    _run(f.inlet(body1, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert f._asked[('u1', 'c1')] == {1000}

    body2 = {
        'model': 'rm-assistent',
        # 20040 chars → ~5010 tokens, crosses 5000
        'messages': [_msg('system', 40), _msg('user', 20000)],
    }
    out = _run(f.inlet(body2, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert '[Systeem-signaal' in out['messages'][0]['content']
    assert '5.000' in out['messages'][0]['content']
    assert f._asked[('u1', 'c1')] == {1000, 5000}


def test_inlet_separate_chats_track_independently():
    f = _make_filter(thresholds='1000')
    body1 = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    _run(f.inlet(body1, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))

    body2 = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(f.inlet(body2, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c2', 'model_id': 'rm-assistent'}))
    # Different chat — should still inject.
    assert '[Systeem-signaal' in out['messages'][0]['content']
    assert ('u1', 'c1') in f._asked
    assert ('u1', 'c2') in f._asked


def test_inlet_no_op_for_other_models():
    f = _make_filter(thresholds='1000', target_models='rm-assistent')
    body = {
        'model': 'gemini.gemini-2.5-flash-lite',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(
        f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'gemini.gemini-2.5-flash-lite'})
    )
    assert '[Systeem-signaal' not in out['messages'][0]['content']
    assert f._asked == {}


def test_inlet_respects_user_opt_out_dict():
    f = _make_filter(thresholds='1000')
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    user = {'id': 'u1', 'valves': {'enabled': False}}
    out = _run(f.inlet(body, __user__=user, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert '[Systeem-signaal' not in out['messages'][0]['content']


def test_inlet_respects_admin_kill_switch():
    f = _make_filter(thresholds='1000', enabled=False)
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert '[Systeem-signaal' not in out['messages'][0]['content']


def test_inlet_no_op_without_chat_id():
    f = _make_filter(thresholds='1000')
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    # No chat_id in metadata — filter should skip rather than risk
    # cross-chat misattribution.
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'model_id': 'rm-assistent'}))
    assert '[Systeem-signaal' not in out['messages'][0]['content']
    assert f._asked == {}


def test_inlet_no_op_without_user_id():
    f = _make_filter(thresholds='1000')
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(f.inlet(body, __user__={}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert '[Systeem-signaal' not in out['messages'][0]['content']


def test_inlet_inserts_system_message_when_none_present():
    f = _make_filter(thresholds='1000')
    body = {
        'model': 'rm-assistent',
        'messages': [_msg('user', 4000)],
    }
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert out['messages'][0]['role'] == 'system'
    assert '[Systeem-signaal' in out['messages'][0]['content']


def test_inlet_picks_highest_crossed_threshold_on_first_call():
    """If the first call already exceeds multiple thresholds (e.g. on a
    long imported chat), we should inject for the highest one — asking
    about a tiny threshold the user blew past long ago is a worse UX."""
    f = _make_filter(thresholds='1000,5000,20000')
    body = {
        'model': 'rm-assistent',
        # 24000 chars → ~6000 tokens, crosses 1000 and 5000 but not 20000
        'messages': [_msg('system', 40), _msg('user', 24000)],
    }
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    assert '5.000' in out['messages'][0]['content']
    # Only the highest crossed gets marked; the lower one stays "unasked"
    # and would re-inject on a future call if state survives. That's fine
    # — the user just gets the most relevant prompt for the current size.
    assert f._asked[('u1', 'c1')] == {5000}


def test_inlet_invalid_thresholds_falls_back_to_defaults():
    f = _make_filter(thresholds='not,a,number')
    body = {
        'model': 'rm-assistent',
        # 4000 chars → 1000 tokens — well below default 100k
        'messages': [_msg('system', 40), _msg('user', 4000)],
    }
    out = _run(f.inlet(body, __user__={'id': 'u1'}, __metadata__={'chat_id': 'c1', 'model_id': 'rm-assistent'}))
    # Defaults start at 100k; 1000 tokens is below. Filter should no-op cleanly.
    assert '[Systeem-signaal' not in out['messages'][0]['content']
