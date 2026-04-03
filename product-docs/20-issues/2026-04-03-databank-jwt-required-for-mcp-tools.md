# Databank MCP Tools — JWT Required in Addition to API Key

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-Databank + MCP Databank Server
**Phase found:** 3

## Description

The Databank API requires both API key auth AND JWT token for document routes. The MCP server sends the API key (which now validates), but doesn't send a JWT. The document routes return "No token provided" after API key auth passes.

## Chain of auth

1. Chatbot → MCP Server: X-API-Key header (works)
2. MCP Server → Databank Backend: X-API-Key header (works after registering key in DB)
3. Databank Backend: API key validates, but document router also requires JWT → "No token provided"

## Fix options

1. **Make API key sufficient for MCP routes** — if API key is valid, skip JWT check for service-to-service calls
2. **Have MCP server generate/forward a service JWT** — create a service account token
3. **Add a bypass flag** — when request comes with valid API key, treat as authenticated service

This is the same issue noted in project memory: "direct app tools need Clerk JWT fix".
