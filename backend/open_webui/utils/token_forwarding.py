"""
Token forwarding utility for Ruimtemeesters app integrations.

Extracts the user's Clerk OAuth token from the OpenWebUI request
and forwards it to downstream app APIs, so each app can verify
the user's identity via its own Clerk middleware.

Usage in OpenWebUI Tools:

    from open_webui.utils.token_forwarding import get_auth_headers

    async def my_tool(self, query: str, __request__=None, __user__: dict = {}) -> str:
        headers = get_auth_headers(__request__)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
"""

import logging
import os
from typing import Optional

from fastapi import Request

log = logging.getLogger(__name__)
ALLOW_SESSION_COOKIE_FORWARDING = os.environ.get('ALLOW_SESSION_COOKIE_FORWARDING', '').lower() in {'1', 'true', 'yes'}


def get_auth_headers(
    request: Optional[Request] = None,
    api_key: str = '',
) -> dict:
    """
    Build auth headers for forwarding to RM app APIs.

    Priority:
    1. Clerk OAuth ID token (from oauth_id_token cookie) — forwarded as Bearer token
    2. Clerk shared session cookie (__session) only when explicitly enabled
    3. Service API key (from tool Valves) — forwarded as X-API-Key
    4. Empty dict (no auth)

    The Clerk ID token is preferred because it carries the user's identity,
    allowing apps to apply per-user RBAC. Service API keys bypass user context.
    """
    headers: dict = {}

    # Try Clerk token from the OIDC flow
    if request is not None:
        # The oauth_id_token cookie is set during OIDC callback
        clerk_token = request.cookies.get('oauth_id_token')
        if clerk_token:
            headers['Authorization'] = f'Bearer {clerk_token}'
            return headers

        # Shared browser session cookies are more sensitive than API tokens.
        # Only forward them when explicitly opted in for a trusted internal setup.
        session_token = request.cookies.get('__session')
        if session_token and ALLOW_SESSION_COOKIE_FORWARDING:
            headers['Authorization'] = f'Bearer {session_token}'
            return headers

    # Fallback: service API key
    if api_key:
        headers['X-API-Key'] = api_key

    return headers
