"""
title: Citation Links
author: Ruimtemeesters
date: 2026-05-16
version: 1.0.0
license: MIT
description: Post-process the assistant's response to turn bare ECLI references and Databank doc-ids into clickable markdown links.
"""

# Outlet filter. The LLM frequently mentions ECLI codes
# (e.g. "ECLI:NL:RBAMS:2024:1234") and Databank document ids when citing
# sources — but unless it remembers to wrap them in markdown link syntax
# the chatbot renders them as plain text. Advisors lose the click-to-source
# affordance and have to copy-paste the identifier into another tab.
#
# This filter sweeps the assistant message after the LLM has produced it,
# finds bare ECLIs and bare doc_id mentions, and rewrites them as markdown
# links. Idempotent: a line that already wraps the identifier in `[...]()`
# is skipped. Roadmap Phase 3 must-do "Citation links in chatbot
# responses (click to view the source document)".

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ECLI grammar per https://www.rechtspraak.nl/uitspraken/Paginas/ECLI-overzicht.aspx :
#   ECLI:<country>:<court>:<year>:<sequence>
# Country is always NL for Dutch jurisprudence; court is 1–7 letters/digits;
# year is 4 digits; sequence is 1–10 alphanumeric (+ optional letter suffix).
ECLI_RE = re.compile(
    r'\bECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Z0-9]{1,10}\b',
)

# Databank document ids today are 8+ char alphanumeric tokens often prefixed
# by `doc_id:` or `(doc_id: ...)` when the LLM cites them. We match the
# explicit form only — bare hex strings would have too many false positives.
# The lookbehind only excludes `[` so we don't re-match inside an already-
# created `[doc_id: …](url)` label. Bare-`(` is allowed because the LLM
# routinely writes `(doc_id: abc12345xyz)` in prose — those need to wrap.
# Idempotency for the broader `[label](url)` construct lives in
# `_inside_existing_markdown_link`, which walks back from each match.
DOC_ID_RE = re.compile(
    r'(?<!\[)\bdoc_id:\s*([A-Za-z0-9_-]{8,})\b',
)


def _ecli_url(ecli: str) -> str:
    return f'https://uitspraken.rechtspraak.nl/details?id={ecli}'


def _doc_url(base: str, doc_id: str) -> str:
    base = base.rstrip('/')
    return f'{base}/documents/{doc_id}'


def _inside_existing_markdown_link(text: str, start: int) -> bool:
    """True when `start` falls inside a markdown link construct
    `[label](url)` — either inside the label or inside the url. The
    heuristic walks back from `start`: if we find `[` before any
    intervening `]` we're inside a label; if we find `](` before any
    intervening `)` we're inside a url target. Either way we should
    not re-wrap the match."""
    # Walk back up to ~200 chars; markdown link constructs rarely span more.
    end = max(0, start - 200)
    inside_label = False
    inside_url = False
    i = start - 1
    while i >= end:
        ch = text[i]
        if ch == ']':
            # Saw closing bracket of an earlier link — we're outside any
            # label that started before this point.
            break
        if ch == '[':
            inside_label = True
            break
        if ch == ')':
            # Saw closing paren of an earlier link target — outside.
            break
        if ch == '(' and i > 0 and text[i - 1] == ']':
            inside_url = True
            break
        i -= 1
    return inside_label or inside_url


def _wrap_ecli(text: str) -> str:
    """Replace bare ECLI occurrences with markdown links, leaving ECLIs
    already inside `[label](url)` constructs untouched."""

    def repl(match: re.Match) -> str:
        ecli = match.group(0)
        if _inside_existing_markdown_link(text, match.start()):
            return ecli
        # Skip when the ECLI is part of a URL (e.g. `?id=ECLI:...`).
        before = text[max(0, match.start() - 1):match.start()]
        if before in ('=', '/'):
            return ecli
        return f'[{ecli}]({_ecli_url(ecli)})'

    return ECLI_RE.sub(repl, text)


def _wrap_doc_id(text: str, base_url: str) -> str:
    """Replace `doc_id: <id>` occurrences with a markdown link. Skips
    occurrences already inside an existing markdown link."""

    def repl(match: re.Match) -> str:
        doc_id = match.group(1)
        if _inside_existing_markdown_link(text, match.start()):
            return match.group(0)
        return f'[doc_id: {doc_id}]({_doc_url(base_url, doc_id)})'

    return DOC_ID_RE.sub(repl, text)


def annotate(content: str, base_url: str) -> str:
    """Pure transform: ECLIs and `doc_id: …` mentions become markdown
    links. Exported for direct unit testing."""
    if not isinstance(content, str) or not content:
        return content
    out = _wrap_ecli(content)
    out = _wrap_doc_id(out, base_url)
    return out


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=20,
            description=(
                'Filter priority (lower = earlier). Outlet pipeline; runs '
                'after the model has produced the assistant message.'
            ),
        )
        databank_base_url: str = Field(
            default='https://databank.datameesters.nl',
            description=(
                'Base URL used when linking `doc_id: …` mentions. The filter '
                'appends `/documents/<id>` to form the target.'
            ),
        )
        enabled: bool = Field(
            default=True,
            description='Master kill switch (admin-level).',
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True,
            description=(
                'Auto-link citations in this chat. Disable to see raw '
                'ECLI / doc_id strings instead of clickable links.'
            ),
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    def _user_disabled(self, user: dict) -> bool:
        user_valves = user.get('valves')
        if isinstance(user_valves, self.UserValves):
            return not user_valves.enabled
        if isinstance(user_valves, dict):
            return user_valves.get('enabled') is False
        return False

    async def outlet(self, body: dict, user: dict | None = None) -> dict:
        """Walk every assistant message in the body and rewrite citations.
        Read-mostly: only mutates message `content` strings."""
        if not self.valves.enabled:
            return body
        if user and self._user_disabled(user):
            return body

        messages = body.get('messages') if isinstance(body, dict) else None
        if not isinstance(messages, list):
            return body

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get('role') != 'assistant':
                continue
            content = msg.get('content')
            if isinstance(content, str):
                msg['content'] = annotate(content, self.valves.databank_base_url)
            elif isinstance(content, list):
                # OpenAI-style content parts; only text parts get rewritten.
                for part in content:
                    if (
                        isinstance(part, dict)
                        and part.get('type') == 'text'
                        and isinstance(part.get('text'), str)
                    ):
                        part['text'] = annotate(part['text'], self.valves.databank_base_url)
        return body
