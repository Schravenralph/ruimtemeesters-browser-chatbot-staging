# ADR-0010: LiteLLM proxy for provider routing and cost management

**Date:** 2026-04-17
**Status:** Proposed

## Context

The chatbot connects directly to multiple LLM providers (Ollama, OpenAI, Anthropic). As usage grows across multiple users and surfaces, there is no centralized way to:

- Track per-user or per-team token spend
- Set budget limits
- Route between providers based on model selection or fallback rules
- Get a unified view of cost across all providers

OpenWebUI supports LiteLLM as a provider natively — no code changes needed.

## Decision

Deploy a **LiteLLM proxy** between OpenWebUI and LLM providers.

```
OpenWebUI ──► LiteLLM Proxy ──┬──► Anthropic (Claude)
                               ├──► OpenAI (GPT-4o/4.1)
                               └──► Ollama (local)
```

LiteLLM handles:

- **Provider routing:** Route requests to the correct provider based on model name
- **Per-user spend tracking:** Budget visibility without custom metering code
- **Fallback chains:** If one provider is down or rate-limited, route to another
- **Prompt caching pass-through:** Anthropic's prompt caching works through LiteLLM

## Rationale

- OpenWebUI already supports LiteLLM as a provider — configuration change, not code change
- Per-user spend tracking becomes critical when multiple users share API costs (vs. per-seat subscriptions)
- Fallback routing improves reliability without retry logic in the chatbot
- Single place to manage API keys, rate limits, and model aliases
- Cost transparency: know exactly what each user/assistant/model costs

## Consequences

- One more container in the Docker Compose stack
- LiteLLM's PostgreSQL can share the existing chatbot DB instance or use its own
- API keys move from OpenWebUI config to LiteLLM config
- OpenWebUI sees LiteLLM as a single OpenAI-compatible endpoint — all provider-specific config lives in LiteLLM
- Adds a network hop (~1ms latency) between OpenWebUI and providers — negligible vs. LLM inference time
