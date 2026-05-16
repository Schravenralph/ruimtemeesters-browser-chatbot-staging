import asyncio
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filters import citation_links  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ----- annotate (pure transform) -----


def test_wraps_bare_ecli_in_markdown_link():
    text = 'Zie de uitspraak ECLI:NL:RBAMS:2024:1234 voor context.'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    assert (
        '[ECLI:NL:RBAMS:2024:1234](https://uitspraken.rechtspraak.nl/details?id=ECLI:NL:RBAMS:2024:1234)'
        in out
    )


def test_wraps_multiple_eclis_in_one_paragraph():
    text = 'Vergelijk ECLI:NL:RVS:2023:4567 met ECLI:NL:HR:2022:8901.'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    assert out.count('](https://uitspraken.rechtspraak.nl/') == 2


def test_does_not_double_wrap_ecli_inside_existing_link():
    text = '[ECLI:NL:RBAMS:2024:1234](https://example.com/x)'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    # The inner ECLI shouldn't get a second `](rechtspraak...)` appended.
    assert out.count('](https://') == 1


def test_wraps_doc_id_mention_with_databank_base_url():
    text = 'Bron: doc_id: abc12345xyz beschrijft het beleid.'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    assert (
        '[doc_id: abc12345xyz](https://databank.datameesters.nl/documents/abc12345xyz)'
        in out
    )


def test_wraps_parenthesized_doc_id_form():
    """The LLM frequently cites in `(doc_id: ...)` form — verify the
    surrounding `(` doesn't block the lookbehind from matching.
    Idempotency for already-wrapped `[label](url)` still works because
    `_inside_existing_markdown_link` walks back from each match."""
    text = 'Het beleid is vastgelegd (doc_id: abc12345xyz) in 2024.'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    assert '[doc_id: abc12345xyz](https://databank.datameesters.nl/documents/abc12345xyz)' in out
    # And the parens around the now-link are preserved verbatim.
    assert '([doc_id: abc12345xyz]' in out
    assert 'abc12345xyz)' in out


def test_idempotent_on_already_wrapped_doc_id_inside_parens():
    """Pre-existing `(text [doc_id: abc...](url) more)` shouldn't be
    re-wrapped: the `[` lookbehind blocks re-match, AND
    `_inside_existing_markdown_link` would also catch label-internal
    matches."""
    pre = '([doc_id: abc12345xyz](https://databank.datameesters.nl/documents/abc12345xyz))'
    out = citation_links.annotate(pre, 'https://databank.datameesters.nl')
    # No double-wrap of the same id.
    assert out.count('[doc_id: abc12345xyz]') == 1


def test_trailing_slash_on_base_url_is_normalised():
    text = 'doc_id: abc12345xyz'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl/')
    assert 'datameesters.nl/documents/abc12345xyz' in out
    assert 'datameesters.nl//documents' not in out


def test_does_not_wrap_short_doc_id_below_min_length():
    text = 'doc_id: abc'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    # 3-char id should not match the >=8 length floor.
    assert '](https://' not in out


def test_does_not_match_inside_url():
    text = 'https://uitspraken.rechtspraak.nl/details?id=ECLI:NL:RBAMS:2024:1234'
    out = citation_links.annotate(text, 'https://databank.datameesters.nl')
    # Already part of a URL — shouldn't re-wrap.
    assert out == text


def test_handles_empty_or_non_string_input():
    assert citation_links.annotate('', 'https://x') == ''
    assert citation_links.annotate(None, 'https://x') is None  # type: ignore[arg-type]


# ----- Filter.outlet (the OpenWebUI integration point) -----


def test_outlet_rewrites_assistant_message_content_string():
    f = citation_links.Filter()
    body = {
        'messages': [
            {'role': 'user', 'content': 'Wat zegt ECLI:NL:RBAMS:2024:1234?'},
            {'role': 'assistant', 'content': 'Volgens ECLI:NL:RBAMS:2024:1234 …'},
        ]
    }
    out = run(f.outlet(body, user={}))
    assert (
        '[ECLI:NL:RBAMS:2024:1234](https://uitspraken.rechtspraak.nl/details?id=ECLI:NL:RBAMS:2024:1234)'
        in out['messages'][1]['content']
    )
    # User message stays untouched (only assistant gets linkified).
    assert out['messages'][0]['content'] == 'Wat zegt ECLI:NL:RBAMS:2024:1234?'


def test_outlet_rewrites_openai_style_content_parts():
    f = citation_links.Filter()
    body = {
        'messages': [
            {
                'role': 'assistant',
                'content': [
                    {'type': 'text', 'text': 'Bron ECLI:NL:HR:2022:8901.'},
                    {'type': 'image', 'image_url': 'https://example.com/x.png'},
                ],
            }
        ]
    }
    out = run(f.outlet(body, user={}))
    text_part = out['messages'][0]['content'][0]['text']
    assert '](https://uitspraken.rechtspraak.nl/' in text_part


def test_outlet_skips_when_master_kill_switch_disabled():
    f = citation_links.Filter()
    f.valves.enabled = False
    body = {
        'messages': [
            {'role': 'assistant', 'content': 'ECLI:NL:RBAMS:2024:1234'},
        ]
    }
    out = run(f.outlet(body, user={}))
    assert out['messages'][0]['content'] == 'ECLI:NL:RBAMS:2024:1234'


def test_outlet_skips_when_user_opted_out_via_uservalves_dict():
    f = citation_links.Filter()
    body = {
        'messages': [
            {'role': 'assistant', 'content': 'ECLI:NL:RBAMS:2024:1234'},
        ]
    }
    out = run(f.outlet(body, user={'valves': {'enabled': False}}))
    assert out['messages'][0]['content'] == 'ECLI:NL:RBAMS:2024:1234'


def test_outlet_tolerates_missing_messages():
    f = citation_links.Filter()
    out = run(f.outlet({}, user={}))
    assert out == {}


def test_uses_configured_databank_base_url():
    f = citation_links.Filter()
    f.valves.databank_base_url = 'https://staging.databank.example/'
    body = {
        'messages': [
            {'role': 'assistant', 'content': 'doc_id: longerthan8chars'},
        ]
    }
    out = run(f.outlet(body, user={}))
    assert 'staging.databank.example/documents/longerthan8chars' in out['messages'][0]['content']
