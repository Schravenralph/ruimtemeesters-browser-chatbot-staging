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
