"""User-facing BFF for the Ruimtemeesters skills corpus (rm-skills).

Read-only proxy that surfaces the persona's mandatory skill list to the
chatbot frontend so a navbar chip can show "Skills: N" without giving
the frontend the gateway bearer or direct rm-skills access.

Same gateway-token pattern as rm_memory.py: `SKILLS_GATEWAY_TOKEN`
matches an entry in rm-skills's `SKILLS_API_KEYS`. The BFF also
forwards `X-Forwarded-User` so rm-skills can future-extend with
per-user filtering (Phase D in the rm-skills roadmap).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from open_webui.models.functions import Functions
from open_webui.utils.auth import get_verified_user
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter()


DEFAULT_SKILLS_URL = 'http://rm-skills:4101'
SKILLS_TIMEOUT_S = 5.0
MAX_SKILLS = 5  # Must match skills_context filter's Valves.max_skills default.
SKILLS_CONTEXT_FUNCTION_ID = 'skills_context'

PERSONA = Literal['ro-assistent', 'juridisch-assistent', 'commercieel-assistent']


class ActiveSkill(BaseModel):
    """Subset of rm-skills's IndexEntry — just what the chip renders."""

    name: str
    description: str


class ActiveSkillsOutput(BaseModel):
    persona: str
    skills: list[ActiveSkill] = Field(default_factory=list)


def _resolve_skills_url() -> str:
    return (os.environ.get('SKILLS_API_URL') or DEFAULT_SKILLS_URL).strip() or DEFAULT_SKILLS_URL


def _resolve_gateway_token() -> str:
    token = (os.environ.get('SKILLS_GATEWAY_TOKEN') or '').strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='SKILLS_GATEWAY_TOKEN not configured — the rm-skills BFF is offline until an operator sets it.',
        )
    return token


def _forwarded_user_id(user: Any) -> str | None:
    """Construct the canonical `clerk:<sub>` identifier from the user's
    OAuth profile. Mirror of rm_memory._forwarded_user_id — the BFF
    convention is the same across both services."""
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


def _user_opted_out(user: Any) -> bool:
    """Check whether the user disabled skills_context via UserValves."""
    user_id = getattr(user, 'id', None)
    if not user_id:
        return False
    try:
        valves = Functions.get_user_valves_by_id_and_user_id(SKILLS_CONTEXT_FUNCTION_ID, user_id)
        if isinstance(valves, dict) and valves.get('enabled') is False:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


@router.get('/active', response_model=ActiveSkillsOutput)
async def list_active_skills(
    persona: PERSONA = Query(
        ..., description='Persona slug — ro-assistent | juridisch-assistent | commercieel-assistent.'
    ),
    user=Depends(get_verified_user),
) -> ActiveSkillsOutput:
    """List the persona's mandatory skills (name + description only).

    The set returned here is exactly the set the `skills_context` inlet
    filter injects into the system prompt — the chip cannot drift from
    what the LLM actually sees.

    Returns an empty list if rm-skills has no mandatory entries for this
    persona; never returns 404. Transport / parser failures map to 502.
    Returns an empty list when the user has opted out of skills_context.
    """
    if _user_opted_out(user):
        return ActiveSkillsOutput(persona=persona, skills=[])

    headers = {
        'Authorization': f'Bearer {_resolve_gateway_token()}',
        'Accept': 'application/json',
    }
    forwarded = _forwarded_user_id(user)
    if forwarded:
        headers['X-Forwarded-User'] = forwarded

    base_url = _resolve_skills_url().rstrip('/')
    url = f'{base_url}/api/v1/skills'

    try:
        async with httpx.AsyncClient(timeout=SKILLS_TIMEOUT_S) as client:
            resp = await client.get(url, params={'persona': persona}, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

            mandatory = _parse_mandatory(payload)

            # Verify each mandatory skill has a fetchable body with
            # non-empty skill_md — skills whose body fetch fails are not
            # injected by the filter, so the chip shouldn't show them.
            verified: list[ActiveSkill] = []
            for skill in mandatory:
                body_url = f'{base_url}/api/v1/skills/{skill.name}'
                try:
                    body_resp = await client.get(body_url, headers=headers)
                    body_resp.raise_for_status()
                    body_data = body_resp.json()
                    if isinstance(body_data, dict) and body_data.get('skill_md'):
                        verified.append(skill)
                except (httpx.HTTPError, ValueError):
                    log.debug('Skipping skill %s — body fetch failed', skill.name)
                    continue

    except httpx.HTTPStatusError as e:
        upstream = ''
        if e.response is not None:
            try:
                upstream = (e.response.text or '')[:500]
            except Exception:  # noqa: BLE001 — defensive read
                upstream = ''
        log.warning('rm-skills returned %s for /api/v1/skills', e.response.status_code if e.response else '?')
        suffix = f' — {upstream}' if upstream else ''
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-skills returned an error: {e}{suffix}',
        ) from e
    except (httpx.HTTPError, ValueError) as e:
        log.warning('rm-skills transport / parse failure: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'rm-skills unreachable or returned invalid JSON: {e}',
        ) from e

    return ActiveSkillsOutput(persona=persona, skills=verified)


def _parse_mandatory(payload: Any) -> list[ActiveSkill]:
    """Extract `mandatory: true` entries from rm-skills's list response.

    Accepts either `{skills: [...]}` (canonical) or a bare list (some
    early endpoints). Returns an empty list on any unexpected shape —
    a chip showing 0 is less surprising than a 502.

    Truncates to MAX_SKILLS to match the skills_context filter's cap.
    """
    raw = payload.get('skills') if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        log.warning('rm-skills returned unexpected payload shape: %r', type(raw))
        return []
    out: list[ActiveSkill] = []
    for s in raw:
        if not isinstance(s, dict) or not s.get('mandatory'):
            continue
        name = s.get('name')
        if isinstance(name, str) and name:
            out.append(ActiveSkill(name=name, description=s.get('description') or ''))
        if len(out) >= MAX_SKILLS:
            break
    return out
