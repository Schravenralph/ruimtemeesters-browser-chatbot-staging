# ADR-0006: LLM Infrastructure

**Date:** 2026-04-04
**Status:** Superseded by Platform ADR-0001

## Decision

See [Platform ADR-0001: Shared Ollama Infrastructure](https://github.com/Schravenralph/Ruimtemeesters-Platform/blob/main/adr/ADR-0001-shared-ollama-infrastructure.md).

This chatbot owns the canonical Ollama container (`rm-ollama`) defined in `docker-compose.rm.yaml`. The model, runtime, and topology decisions are documented at the platform level because they affect all repos.

## Chatbot-specific notes

- Assistants use `qwen2.5:7b-instruct-q5_K_M` as `base_model_id`
- Tool-calling responses take ~40-100s with 3 MCP tools, longer with 8
- The Ruimtemeesters Assistent (8 tools) may timeout — consider reducing tools
