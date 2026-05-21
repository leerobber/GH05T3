# FREE FALLBACK LLM SYSTEM

## Overview
When Anthropic API credits are exhausted or rate-limited, GH05T3 **automatically routes** to free local models without failing.

**Zero downtime. Zero API cost.**

## How It Works

### Automatic Credit Detection
When Claude API returns:
- **429** — Rate limited
- **401** — Invalid/expired key or insufficient credits
- **Quota exceeded** — Daily/monthly limit hit
- **Payment issues** — Billing problem

→ System instantly routes to free fallback

### Degradation Chain (Fastest to Most Resilient)
```
1. vLLM (RTX 5050)           — 70B model, fastest
   ↓ (if timeout/offline)
2. llama.cpp verifier (780M) — Mid-tier, stable
   ↓ (if timeout/offline)
3. llama.cpp CPU             — Always available, slowest
   ↓ (if all offline)
   → Returns error with helpful message
```

## Usage

### For Developers
**No code changes needed.** The fallback is transparent:

```python
# This works exactly the same with or without API credits
client = ClaudeClient(api_key="sk-...")
content, usage = await client.call(
    system="You are an expert...",
    user="Analyze this code...",
    role_label="architect",
    task_label="code_review",
)
# If credits exhausted, automatically uses local LLM instead
```

### Monitoring Fallback Events

Check the SwarmBus `#fallback` channel in the dashboard:
- All fallback activations logged
- Which tier was used (vLLM, llama_verifier, llama_cpu)
- Token counts and latency
- Reason for fallback (credit exhaustion detected)

## Configuration

### Endpoints (in `backend/integrations/fallback_llm.py`)
```python
VLLM_URL = "http://localhost:8010/v1/chat/completions"
LLAMA_VERIFIER_URL = "http://localhost:8011/v1/chat/completions"
LLAMA_CPU_URL = "http://localhost:8012/v1/chat/completions"
```

Update these if your local model ports differ.

### Models (customize as needed)
```python
VLLM_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
LLAMA_MODEL = "llama2"
```

## What Still Costs Money
Nothing changes — Claude API calls work the same when you have credits.

When you **don't** have credits:
- **Zero cost** — uses local models
- **Full functionality** — training, architecture review, evaluation all work
- **Slower** — local models are 5-10x slower than Claude, but still capable

## Testing

Run the test suite:
```bash
python test_fallback.py
```

Expected output:
```
Testing credit exhaustion detection:
  PASS: '429 rate limit exceeded' -> True
  PASS: '401 unauthorized' -> True
  PASS: Credit quota exhausted' -> True
  ...

Fallback LLM system initialized and ready.
```

## Real-World Scenarios

### Scenario 1: API goes down mid-training
```
[Claude] 429 rate limit exceeded
[Claude] Routing to free local LLM fallback...
[Fallback] vLLM: 340 tokens, 890ms
→ Training continues using vLLM
```

### Scenario 2: Monthly quota exhausted
```
[Claude] API credits exhausted or rate limited
[Claude] Routing to free local LLM fallback...
[Fallback] vLLM: 512 tokens, 1200ms
[Fallback] KAIROS cycle generated (via free model)
→ Next month: automatically reverts to Claude when credits available
```

### Scenario 3: vLLM offline
```
[Fallback] vLLM failed: Connection refused
[Fallback] llama_verifier: 280 tokens, 2100ms
→ Falls back to Radeon 780M, slightly slower but functional
```

## Performance Impact

| Model | Latency | Cost |
|-------|---------|------|
| Claude Sonnet | 500-800ms | $3/M input, $15/M output |
| vLLM 70B | 800-1500ms | **FREE** |
| llama.cpp (780M) | 2-4s | **FREE** |
| llama.cpp (CPU) | 10-30s | **FREE** |

Fallback is ~2-5x slower but **zero cost**.

## Architecture

```
ClaudeClient.call()
    ↓
    Try Anthropic API (if key configured & paid)
        ↓ (on 429/401/quota error)
        Detect credit exhaustion
        ↓
    FallbackLLMClient.call()
        ↓
        Try vLLM (port 8010)
            ↓ (timeout/offline)
        Try llama_verifier (port 8011)
            ↓ (timeout/offline)
        Try llama_cpu (port 8012)
            ↓ (all offline)
        Return error message
```

## Emergency: All Local Models Offline

If vLLM and llama.cpp are all unreachable:
```
[Fallback] All fallback endpoints exhausted — no local models available
```

**Fix:**
```bash
# Start vLLM on port 8010
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.3-70B-Instruct --port 8010

# Or start llama.cpp
./llama-server -m model.gguf -ngl 30 --port 8011
```

## Future Enhancements

- [ ] Metrics: track fallback frequency, token savings
- [ ] Cost calculator: show hypothetical Claude cost if models weren't available
- [ ] Dynamic model selection: choose vLLM vs llama.cpp based on workload
- [ ] Context caching: cache common system prompts across fallback calls
- [ ] Graceful degradation: reduce max_tokens if local models overloaded

## Questions?

Check SwarmBus logs or `backend/integrations/fallback_llm.py` for full implementation.
