"""Unit tests for backend/open_webui/utils/forwarded_user.py.

The helper is shared by the rm-memory BFF (routers/rm_memory.py) and
the chat-side MCP client setup (utils/middleware.py). The first
regressed in Memory#54/Chatbot#58 when it inspected the wrong oauth
key; the second regressed in Chatbot#158 when the helper was never
called at all and chat tool-calls landed under `api:mcp-shim`. These
tests pin both the identity construction and the header-mutation
contract that middleware.py relies on.

Run with:
    pytest backend/open_webui/test/util/test_forwarded_user.py -v
"""

from __future__ import annotations

from types import SimpleNamespace

from open_webui.utils.forwarded_user import (
    apply_forwarded_user_header,
    forwarded_user_id,
)


# --- forwarded_user_id -----------------------------------------------------


def test_forwarded_user_id_returns_clerk_prefix_for_oidc_oauth():
    user = SimpleNamespace(oauth={'oidc': {'sub': 'user_abc123'}})
    assert forwarded_user_id(user) == 'clerk:user_abc123'


def test_forwarded_user_id_returns_none_when_oauth_missing():
    user = SimpleNamespace()
    assert forwarded_user_id(user) is None

    user = SimpleNamespace(oauth=None)
    assert forwarded_user_id(user) is None


def test_forwarded_user_id_returns_none_when_oauth_lacks_oidc():
    user = SimpleNamespace(oauth={})
    assert forwarded_user_id(user) is None

    user = SimpleNamespace(oauth={'google': {'sub': 'google_42'}})
    assert forwarded_user_id(user) is None


def test_forwarded_user_id_returns_none_when_oidc_sub_missing():
    user = SimpleNamespace(oauth={'oidc': {}})
    assert forwarded_user_id(user) is None

    user = SimpleNamespace(oauth={'oidc': {'sub': ''}})
    assert forwarded_user_id(user) is None

    user = SimpleNamespace(oauth={'oidc': {'sub': None}})
    assert forwarded_user_id(user) is None


def test_forwarded_user_id_returns_none_when_oauth_is_not_a_dict():
    user = SimpleNamespace(oauth='not-a-dict')
    assert forwarded_user_id(user) is None


def test_forwarded_user_id_ignores_legacy_clerk_key():
    # Earlier callers wrote `oauth['clerk']` directly; the OWUI OIDC integration
    # actually stores under the literal `'oidc'` key. A user whose only entry
    # lives under 'clerk' must still resolve to None so we don't silently mask
    # the misconfiguration.
    user = SimpleNamespace(oauth={'clerk': {'sub': 'user_abc'}})
    assert forwarded_user_id(user) is None


# --- apply_forwarded_user_header -------------------------------------------
# Regression cover for Chatbot#158: utils/middleware.py builds the MCP
# connect headers dict and must stamp X-Forwarded-User on it before
# MCPClient.connect() so the chat tool-call carries the Clerk identity.


def test_apply_forwarded_user_header_sets_clerk_id_for_oidc_user():
    headers: dict[str, str] = {'Authorization': 'Bearer gateway-token'}
    user = SimpleNamespace(oauth={'oidc': {'sub': 'user_xyz'}})

    apply_forwarded_user_header(headers, user)

    assert headers['X-Forwarded-User'] == 'clerk:user_xyz'
    assert headers['Authorization'] == 'Bearer gateway-token'


def test_apply_forwarded_user_header_no_op_for_user_without_oidc():
    # No sub → fall back to the gateway api: principal downstream.
    # The header must be absent, not empty, so rm-memory's
    # FORWARDED_ID_RE doesn't trip on a blank value.
    headers: dict[str, str] = {'Authorization': 'Bearer gateway-token'}
    user = SimpleNamespace(oauth={})

    apply_forwarded_user_header(headers, user)

    assert 'X-Forwarded-User' not in headers
    assert headers == {'Authorization': 'Bearer gateway-token'}


def test_apply_forwarded_user_header_overwrites_prior_value():
    # If something upstream (e.g. include_user_info_headers under
    # ENABLE_FORWARD_USER_INFO_HEADERS) already wrote a non-canonical
    # X-Forwarded-User, the canonical clerk:<sub> wins. rm-memory's
    # invariant is one identity convention; never two.
    headers: dict[str, str] = {'X-Forwarded-User': 'email:ralph@example.com'}
    user = SimpleNamespace(oauth={'oidc': {'sub': 'user_ralph'}})

    apply_forwarded_user_header(headers, user)

    assert headers['X-Forwarded-User'] == 'clerk:user_ralph'
