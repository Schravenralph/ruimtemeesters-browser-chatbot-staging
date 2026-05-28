"""Pydantic schema for scripts/personas.yaml — see ADR-0018."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ConnectionDef(BaseModel):
    base_urls: list[str]
    default_model: str
    disable: list[str] = Field(default_factory=list)


class FilterDef(BaseModel):
    id: str
    name: str
    source_path: str
    description: str
    needs_memory_token: bool = False
    needs_skills_token: bool = False
    valves_extras: dict = Field(default_factory=dict)


class SuggestionPrompt(BaseModel):
    content: str
    title: list[str]


class PersonaDef(BaseModel):
    id: str
    name: str
    description: str
    profile_image_url: str
    system_prompt: str
    tool_ids: list[str] = Field(default_factory=list)
    # Per-persona tool-name allowlist with bare-prefix wildcards.
    # Each entry is either an exact tool name (`bag_info_at_point`) or a
    # prefix pattern ending in `*` (`solar_*` matches every tool whose
    # name starts with `solar_`). Empty list = no tools exposed. The
    # chatbot filter at src/lib/integrations/toolAllowlist/ enforces
    # this at chat-completion assembly time.
    tools: list[str] = Field(default_factory=list)
    filter_ids: list[str] = Field(default_factory=list)
    suggestion_prompts: list[SuggestionPrompt] = Field(default_factory=list)
    capabilities: dict = Field(default_factory=dict)
    default_feature_ids: list[str] = Field(default_factory=list)


class PromptDef(BaseModel):
    command: str
    name: str
    content: str


class Manifest(BaseModel):
    connection: ConnectionDef
    filters: list[FilterDef] = Field(default_factory=list)
    legacy_persona_ids: list[str] = Field(default_factory=list)
    personas: list[PersonaDef]
    prompts: list[PromptDef] = Field(default_factory=list)


def load_manifest(path: Path) -> Manifest:
    with path.open(encoding='utf-8') as fh:
        raw = yaml.safe_load(fh)
    return Manifest.model_validate(raw)
