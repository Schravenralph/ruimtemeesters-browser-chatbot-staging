"""Canonical `clerk:<sub>` identity for X-Forwarded-User propagation.

Shared between the rm-memory BFF (HTTP requests at user-action time)
and the chat-side MCP client setup (tool-call requests during LLM
turns) so a single identity convention reaches every downstream
service. Centralising avoids the failure mode that produced Memory#58
and Chatbot#158: three different code paths each re-deriving the
identity from `user.email`, `user.id`, or `user.name`, none of which
match rm-memory's `FORWARDED_ID_RE = (clerk|api):[A-Za-z0-9_.-]+`.
"""

from __future__ import annotations

from typing import Any, MutableMapping


def forwarded_user_id(user: Any) -> str | None:
    """Construct `clerk:<sub>` from the user's OIDC oauth profile.

    Returns None when no OIDC sub is present; callers must omit the
    X-Forwarded-User header in that case so downstream falls back to
    attributing the request to the gateway's `api:` principal.

    The dict key is `'oidc'` (not `'clerk'`): OWUI's generic OIDC
    integration is registered under the literal string `'oidc'` in
    `OAUTH_PROVIDERS`, and `update_user_oauth_by_id` stores the
    per-provider entry under that key — so a Clerk-OIDC user lands
    as `oauth = {"oidc": {"sub": "user_..."}}`. `OAUTH_PROVIDER_NAME`
    is the display label only; it doesn't influence the dict key.
    """
    oauth = getattr(user, 'oauth', None) or {}
    if not isinstance(oauth, dict):
        return None
    oidc_entry = oauth.get('oidc')
    if not isinstance(oidc_entry, dict):
        return None
    sub = oidc_entry.get('sub')
    if not sub or not isinstance(sub, str):
        return None
    return f'clerk:{sub}'


def apply_forwarded_user_header(headers: MutableMapping[str, str], user: Any) -> None:
    """Set headers['X-Forwarded-User'] to `clerk:<sub>` when the user has
    an OIDC sub, otherwise leave headers untouched. The MCP client passes
    headers at connect time so they persist for the session — every
    subsequent tools/call inherits the identity.
    """
    forwarded = forwarded_user_id(user)
    if forwarded:
        headers['X-Forwarded-User'] = forwarded

