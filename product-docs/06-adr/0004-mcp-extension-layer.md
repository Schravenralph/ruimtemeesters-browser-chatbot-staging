# ADR-0004: MCP extension layer (Phase C)

**Date:** 2026-03-31
**Status:** Planned

## Context

Phase A uses OpenWebUI Python Tools calling REST APIs. Phase C wraps the same APIs as MCP servers, enabling use from Claude Code, Cursor, and other AI tools beyond the chatbot.

## Decision

Build per-app MCP servers (TypeScript, matching RM ecosystem) that wrap app endpoints as MCP tools. OpenWebUI connects via MCP client. Same business logic, different protocol.

## Rationale

- MCP is an open standard — not locked into OpenWebUI's plugin format
- MCP servers can be TypeScript (matches the RM ecosystem)
- Same MCP servers usable from Claude Code, Cursor, and other AI tools
- Zod schemas in the Aggregator can auto-generate MCP tool schemas

## Consequences

- Phase A tools continue to work as fallback
- MCP servers need their own Docker containers
- OpenWebUI's MCP client support may need fork customization
- Enables developer-facing AI tool access to RM data
