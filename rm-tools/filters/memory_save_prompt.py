"""
title: Memory Save Prompt
author: Ruimtemeesters
date: 2026-05-04
version: 1.0.0
license: MIT
description: At configurable conversation-length thresholds, instruct the assistant to ask whether to save key takeaways via summarize_session.
"""

# The trigger ADR-0002 §4 calls for: when a conversation grows past a
# threshold, ask the user whether to promote it into durable memory.
# OpenWebUI has no native session-idle hook, so the cheapest design is a
# context-length-based inlet that injects a one-shot system instruction
# at each threshold crossing. The model handles asking, listening for the
# yes/no, and (on yes) calling `summarize_session` itself — the filter
# only owns the threshold-crossing signal.
#
# State (which thresholds we've already injected for) is per-(user, chat)
# in-memory. Lost on restart, which means at most one extra injection per
# threshold per chat after a process restart. Acceptable for now.

import logging
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


def _approx_tokens(messages: list[dict]) -> int:
    """Estimate the token count of the message list. chars/4 is a stable
    rough approximation for mixed Dutch/English content; we only need it
    to be monotonic and within ~20% — exact thresholds don't matter."""
    if not isinstance(messages, list):
        return 0
    char_count = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get('content')
        if isinstance(content, str):
            char_count += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    char_count += len(part.get('text', '') or '')
    return char_count // 4


def _format_count(n: int) -> str:
    """Dutch thousands separator. 100000 → '100.000'."""
    return f'{n:,}'.replace(',', '.')


def _build_instruction(threshold: int, next_threshold: int | None) -> str:
    """Render the system-prompt block injected when a threshold crosses.

    The block is bracketed as a system signal so the assistant treats it
    as instruction rather than echoing it back to the user verbatim. The
    [Systeem-signaal] tag is mirrored in the rm-assistent system prompt
    so the model knows to treat it as a side-channel cue.
    """
    next_part = (
        f' Als de gebruiker nu nog niet wil opslaan, vraag dan opnieuw rond de {_format_count(next_threshold)} tokens.'
        if next_threshold
        else ''
    )
    return (
        '\n\n---\n'
        '[Systeem-signaal — niet aan de gebruiker tonen]\n'
        f'Het gesprek heeft ongeveer {_format_count(threshold)} tokens bereikt. '
        'Sluit je volgende reactie af met een korte vraag aan de gebruiker: '
        '"Zal ik de belangrijkste punten van dit gesprek opslaan?" '
        'Bij bevestiging: roep `summarize_session` aan op rm-memory en volg de scaffold '
        'die je terugkrijgt (emit per durable observatie een `save_memory` call).'
        f'{next_part}'
    )


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=12,
            description=(
                'Filter priority (lower = earlier). Runs after bopa_session_context '
                '(10) and memory_recall_context (11) so context priming lands first.'
            ),
        )
        thresholds: str = Field(
            default='100000,250000,500000,1000000',
            description=(
                'Comma-separated token thresholds. At the first inlet call where '
                'estimated context tokens >= a threshold not yet asked for this chat, '
                'the filter injects a one-shot system instruction telling the model '
                'to ask the user about saving.'
            ),
        )
        target_models: str = Field(
            default='rm-assistent',
            description='Comma-separated list of model IDs the filter fires for. Other models are no-ops.',
        )
        enabled: bool = Field(
            default=True,
            description='Master kill switch (admin-level). Disable to short-circuit all injection.',
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True,
            description='Enable the save-prompt for this user. Disable to opt out — the assistant will never be nudged to ask about saving in your chats.',
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        # _asked: dict[(user_id, chat_id), set[int]] — thresholds already injected.
        # In-memory; lost on restart by design (see module docstring).
        self._asked: dict[tuple[str, str], set[int]] = {}

    # ----- helpers -----

    def _parse_thresholds(self) -> list[int]:
        try:
            parsed = sorted({int(x.strip()) for x in (self.valves.thresholds or '').split(',') if x.strip()})
            return [t for t in parsed if t > 0]
        except ValueError:
            log.warning('memory_save_prompt: invalid thresholds %r, falling back to defaults', self.valves.thresholds)
            return [100000, 250000, 500000, 1000000]

    def _highest_crossed(self, current_tokens: int, thresholds: list[int]) -> int | None:
        crossed = [t for t in thresholds if current_tokens >= t]
        return max(crossed) if crossed else None

    def _model_id_from_metadata(self, body: dict, metadata: dict | None) -> str:
        if isinstance(metadata, dict):
            mid = metadata.get('model_id') or (metadata.get('model') or {}).get('id')
            if mid:
                return str(mid)
        return str(body.get('model') or '')

    def _model_in_scope(self, body: dict, metadata: dict | None) -> bool:
        targets = {m.strip() for m in (self.valves.target_models or '').split(',') if m.strip()}
        if not targets:
            return True
        return self._model_id_from_metadata(body, metadata) in targets

    def _user_opted_out(self, user: dict) -> bool:
        if not isinstance(user, dict):
            return False
        user_valves = user.get('valves')
        if isinstance(user_valves, self.UserValves):
            return not user_valves.enabled
        if isinstance(user_valves, dict):
            return user_valves.get('enabled') is False
        return False

    def _inject_block(self, body: dict, block: str) -> None:
        """Append block to the existing system message, or insert a new system
        message at position 0 when the body has no system message yet."""
        messages = body.get('messages') or []
        if not (isinstance(messages, list) and messages):
            return
        if messages[0].get('role') == 'system':
            messages[0] = {
                **messages[0],
                'content': (messages[0].get('content') or '') + block,
            }
        else:
            messages = [{'role': 'system', 'content': block.lstrip()}] + messages
        body['messages'] = messages

    # ----- inlet entry point -----

    async def inlet(
        self,
        body: dict,
        __user__: dict | None = None,
        __metadata__: dict | None = None,
        **_: Any,
    ) -> dict:
        try:
            if not self.valves.enabled:
                return body
            user = __user__ or {}
            user_id = str(user.get('id') or '')
            if not user_id or self._user_opted_out(user):
                return body
            if not self._model_in_scope(body, __metadata__):
                return body

            chat_id = ''
            if isinstance(__metadata__, dict):
                chat_id = str(__metadata__.get('chat_id') or '')
            if not chat_id:
                # No chat scope to attribute the threshold-state to. Skipping
                # is safer than risking a misattributed cross-chat injection.
                return body

            messages = body.get('messages') or []
            current_tokens = _approx_tokens(messages)
            thresholds = self._parse_thresholds()
            if not thresholds:
                return body
            crossed = self._highest_crossed(current_tokens, thresholds)
            if crossed is None:
                return body

            asked_set = self._asked.setdefault((user_id, chat_id), set())
            if crossed in asked_set:
                return body

            higher = [t for t in thresholds if t > crossed]
            next_threshold = min(higher) if higher else None

            instruction = _build_instruction(crossed, next_threshold)
            self._inject_block(body, instruction)
            asked_set.add(crossed)
        except Exception as e:
            log.warning('memory_save_prompt: unexpected error, passing body through: %s', e)
        return body
