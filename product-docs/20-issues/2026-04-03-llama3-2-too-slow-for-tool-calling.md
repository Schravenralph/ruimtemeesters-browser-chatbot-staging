# llama3.2:3b Too Slow for Tool-Calling on CPU

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-Browser-Chatbot (Ollama)
**Phase found:** 3

## Description

The llama3.2:3b model running on CPU (Hetzner EX63) is too slow to handle tool-calling requests. When an assistant with MCP tools is selected, the model receives tool specs in the prompt which significantly increases token count. The model maxes out CPU (861%) but fails to produce a response within 5+ minutes.

Basic chat without tools works (response in ~15 seconds). Tool-calling prompts with 3+ MCP tool specs timeout or stall.

## Repro steps

1. Go to chatbot.datameesters.nl
2. Select "Beleidsadviseur" (has 3 tools: databank, geoportaal, aggregator)
3. Send "Hallo, vertel kort wie je bent in 1 zin."
4. Wait 5+ minutes — blinking dot, no response

## Expected

Response within 30 seconds.

## Actual

Model stalls generating with 861% CPU usage. No response after 5+ minutes.

## Notes

Fix options (in order of preference):
1. Use a cloud LLM (OpenAI/Anthropic API) — fast, reliable, supports tool calling natively
2. Add a GPU to the server and use a larger model (llama3.1:8b with GPU)
3. Use a smaller tool-calling-optimized model (e.g., qwen2.5:3b which has better tool support)
4. Reduce the number of tools per assistant to minimize prompt size

The base model works fine for simple chat. The issue is specifically tool-calling overhead.

---

## Resolution

**Status:** RESOLVED on main.

Root cause: CPU-only inference on a 3B model with tool-spec prompt bloat. Resolved by switching the local inference stack:

- Commit `3457fa2cb` — ADR-0006 selected **qwen2.5:7b** as the new local tool-calling model (benchmarked in `06-adr/ADR-0006-local-llm-model.md`).
- Commit `5a1759b1b` — Pass Intel iGPU (`/dev/dri`) to the Ollama container.
- Commit `819bfc7cd` — Switch to IPEX-LLM Ollama build for Intel iGPU acceleration.
- Commit `5fff94717` — `OLLAMA_INTEL_GPU=true` to force GPU path.
- Commit `b341f9667` — Benchmark data + shared-Ollama decision documented.

Verified: the running chatbot now uses `qwen2.5:7b-instruct-q5_K_M` on Intel iGPU via the IPEX-LLM image; tool-calling prompts return in seconds, not minutes.

Note: `rm-tools/register_assistants.py` still carries `BASE_MODEL = "llama3.1:latest"` as the assistants' base — users can switch model per chat, so this is not blocking. Separate cleanup if ever needed.
