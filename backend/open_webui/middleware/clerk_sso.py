"""
FastAPI middleware for Clerk shared-session SSO.

Strategy: Clerk's __session cookie is host-only (datameesters.nl) and does NOT
reach subdomains like chatbot.datameesters.nl. However, the __client_uat cookie
IS set on .datameesters.nl (all subdomains). When we detect __client_uat but no
OpenWebUI token, the user is logged into Clerk elsewhere — we auto-redirect to
the OIDC flow. Since the user already has a Clerk session, the OIDC flow
completes instantly (no login form), and OpenWebUI gets its token seamlessly.

Flow:
1. User visits chatbot.datameesters.nl (no OpenWebUI token)
2. Middleware sees __client_uat cookie → user has a Clerk session
3. Redirect to /oauth/oidc/callback trigger (OpenWebUI's OIDC initiation)
4. Clerk sees the user is logged in → auto-approves → redirects back
5. OpenWebUI creates session token from OIDC response → user is in
"""

import logging
import os

from fastapi import Request
from starlette.responses import RedirectResponse, Response  # noqa: F401

log = logging.getLogger(__name__)

CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")

# Paths to skip — don't intercept API calls, assets, or the OIDC flow itself
SKIP_PREFIXES = (
    "/static/",
    "/brand-assets/",
    "/assets/",
    "/_app/",
    "/health",
    "/ws/",
    "/api/",
    "/ollama/",
    "/openai/",
    "/oauth/",
)


async def clerk_sso_middleware(request: Request, call_next) -> Response:
    """
    Detect Clerk session via __client_uat cookie and auto-redirect to OIDC.

    This gives seamless SSO: users logged into any *.datameesters.nl app
    get into the chatbot without seeing a login page.
    """
    # Skip if Clerk is not configured
    if not CLERK_SECRET_KEY:
        return await call_next(request)

    path = request.url.path

    # Only intercept the /auth page — this is where OpenWebUI's frontend
    # redirects when there's no token. The root / is served as a static
    # prerendered page and doesn't go through ASGI middleware.
    if not path.startswith("/auth"):
        return await call_next(request)

    # Skip if already has an OpenWebUI token
    if request.cookies.get("token"):
        return await call_next(request)

    # Only process HTML page requests (not XHR/fetch)
    accept = request.headers.get("accept", "")
    if "text/html" not in accept:
        return await call_next(request)

    # Check for Clerk __client_uat cookie (set on .datameesters.nl, reaches all subdomains)
    has_clerk_session = any(
        k.startswith("__client_uat") for k in request.cookies.keys()
    )

    if not has_clerk_session:
        log.info("Clerk SSO: /auth page hit but no __client_uat cookie — showing login form")
        return await call_next(request)

    # User has a Clerk session but no OpenWebUI token — redirect to OIDC
    # The OIDC flow will complete instantly because Clerk already has a session
    log.info("Clerk SSO: detected __client_uat at /auth — auto-redirecting to OIDC")

    return RedirectResponse(url="/oauth/oidc/login", status_code=302)
