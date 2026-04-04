# ADR-0006: Shared Ollama Infrastructure — Single IPEX-LLM Instance

**Date:** 2026-04-03, updated 2026-04-04
**Status:** Accepted
**Context:** Choosing the LLM model, runtime, and topology for the Ruimtemeesters stack (Chatbot, Databank, Geoportaal) on shared hardware.

## Decision

1. **One Ollama instance** for the entire stack, running `intelanalytics/ipex-llm-inference-cpp-xpu` with Intel iGPU acceleration via SYCL/oneAPI.
2. **Model: qwen2.5:7b-instruct-q5_K_M** (~5.4GB) as the default.
3. **FIFO queue** (`OLLAMA_NUM_PARALLEL=1`) — serial processing, no concurrent execution.
4. All three LLM consumers (Chatbot, Databank, Geoportaal geo-narrator) connect to the same instance.

## Hardware

Hetzner EX63:
- CPU: Intel Core Ultra 7 265 (20 cores, 5.1 GHz turbo)
- RAM: 62GB (43GB available after all services)
- GPU: Intel Arrow Lake integrated graphics (detected by IPEX-LLM via Level Zero)
- No discrete GPU

## Benchmarks

### Model selection (single request, iGPU)

| Model | RAM | Prompt eval | Generation | Tool-calling |
|-------|-----|-------------|------------|-------------|
| llama3.2:3b Q4_0 | 2GB | 75 tok/s | 20 tok/s | Fails (too small for tool schemas) |
| qwen2.5:7b Q4_0 | 4.7GB | 11 tok/s | 3.2 tok/s | Works but Q4_0 quality is poor |
| **qwen2.5:7b Q5_K_M** | **5.4GB** | **16 tok/s** | **7.0 tok/s** | **Works — best balance** |
| qwen2.5:14b Q4_0 | 9GB | 1.3 tok/s | 0.06 tok/s | Too slow |

### Runtime comparison (qwen2.5:7b Q5_K_M)

| Runtime | Prompt eval | Generation | Speedup |
|---------|-------------|------------|---------|
| Standard Ollama (CPU-only) | 10.9 tok/s | 3.2 tok/s | baseline |
| **IPEX-LLM (iGPU + SYCL)** | **16 tok/s** | **7.0 tok/s** | **2-3x** |

### Topology: one instance vs two (iGPU contention)

| Scenario | Generation | Total time | Notes |
|----------|-----------|------------|-------|
| Single instance, single request | 7.0 tok/s | 40s | Optimal |
| **Two instances, concurrent** | **5.0 tok/s** | **94s** | **29% degradation — iGPU contention** |
| Single instance, queued (FIFO) | 7.0 tok/s | 80s (2 × 40s) | No degradation, just serial |

**Two instances fighting over one iGPU is worse than one instance with a queue.** Concurrent execution degrades both requests. Sequential execution delivers each at full speed.

### Memory pressure impact

| Condition | Generation | Notes |
|-----------|-----------|-------|
| Clean (1 model loaded) | 7.0 tok/s | Normal |
| 3 models loaded (20GB+) | 0.12 tok/s | **58x slower — swap thrashing** |

**Critical: never leave unused models loaded.** Use `OLLAMA_MAX_LOADED_MODELS=1` or clean up regularly.

## LLM Usage by Service

| Service | What it uses LLM for | Model | Frequency | Can share? |
|---------|---------------------|-------|-----------|------------|
| **Chatbot** | Chat + tool-calling | qwen2.5:7b Q5_K_M | Per user message | Yes |
| **Databank** | KG gatekeeper (batch) | llama3.1:8b | Per workflow (background) | Yes |
| **Databank** | Reranking | gpt-4o-mini (OpenAI) | Per workflow | N/A (cloud) |
| **Databank** | RAG Q&A | gpt-4o-mini (OpenRouter) | Per query | N/A (cloud) |
| **Geoportaal** | Geo-narrator prose | llama3.1:8b (Ollama) | On-demand | Yes |
| **Geoportaal** | Geo-narrator tools | gpt-4o-mini (OpenRouter) | On-demand | N/A (cloud) |

The Databank and Geoportaal already offload heavy LLM work (reranking, RAG, tool-calling) to cloud APIs. Their local Ollama usage is limited to batch KG validation and prose generation — low frequency, no real contention with the chatbot.

## Rationale

1. **qwen2.5:7b Q5_K_M is the optimal model** — best tool-calling quality at this size, strong Dutch language support, Q5_K_M has minimal quantization degradation
2. **IPEX-LLM unlocks the iGPU** — 2-3x speedup over CPU-only, Arrow Lake detected via Level Zero
3. **One instance beats two** — iGPU contention (29% degradation) makes concurrent instances counterproductive
4. **FIFO is fine** — interactive chatbot requests are infrequent enough that queuing behind a KG batch job adds seconds, not minutes
5. **Cloud APIs handle the heavy lifting** — Databank and Geoportaal already use OpenAI/OpenRouter for compute-intensive tasks

## Consequences

- Tool-calling responses take ~40-100 seconds (single instance, iGPU)
- If chatbot and KG gatekeeper run simultaneously, one waits ~40s for the other
- The Ruimtemeesters Assistent (8 tools) produces very large prompts — may need tool count reduction
- If faster interactive responses are needed: add OpenRouter as an alternative LLM provider in the chatbot

## Address

22 Avenue Street, Brisbane, QLD 4000
