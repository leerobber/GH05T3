# SovereignNation AI University — Deployment Roadmap

## Phase Overview

| Phase | Focus | Duration | Revenue Gate |
|-------|-------|----------|-------------|
| 0 | Local training complete | Week 1 | — |
| 1 | API MVP live + first 10 users | Weeks 2–4 | $490/mo |
| 2 | AI University beta (50 users) | Month 2 | $2,450/mo |
| 3 | Agent Marketplace launch | Month 3 | $5,000 MRR |
| 4 | Enterprise contracts | Months 4–6 | $15K/mo |
| 5 | Scale + hiring | Month 7+ | $50K+ MRR |

---

## Phase 0 — Training Complete (Week 1)

**Goal:** Fine-tuned LoRA adapters for all 5 agents ready to serve.

### Steps

```bash
# 1. Generate all 95 curriculum pairs
python sovereign_trainer_v5.py --generate-only --domain all

# 2. Run training on GPU pod (RunPod A40 / RTX 4090, 24GB+)
#    Cost: ~$1.50–2.00/hour, 2–4 hours per run
HF_TOKEN=hf_... python sovereign_trainer_v5.py --domain all --mode orpo --push

# 3. Verify adapters pushed to HuggingFace
# tastytator/sovereign-university-lora
# tastytator/sovereign-economy (configs: sft, security, agents, sovereign_v5)
```

### Deliverables
- [ ] `sovereign_v5_adapter/` saved locally
- [ ] Adapter pushed to `tastytator/sovereign-university-lora`
- [ ] `sovereign_v5_pairs.jsonl` (95 DPO pairs) pushed to HF as `sovereign_v5` config
- [ ] All 5 agent LoRAs fine-tuned via `train_sovereign_sft.py --agent all`

---

## Phase 1 — API MVP (Weeks 2–4)

**Goal:** First paying customers. One endpoint, one pricing tier.

### Minimum Viable API

```
POST /v1/chat
Authorization: Bearer sk_...

{
  "agent": "forge",
  "messages": [{"role": "user", "content": "Build a rate limiter"}]
}
```

### Steps

1. **Expose gateway_v3.py** behind nginx with SSL (Let's Encrypt).
2. **Add API key management** — generate `sk_` prefixed keys, store SHA256 hashes in SQLite.
3. **Wire billing** — Stripe Meter API for per-call metering.
4. **Launch page** — single-page with pricing, 3 code examples, Discord invite link.
5. **Seed 10 beta users** — post to HackerNews "Show HN", r/MachineLearning, indie.hackers.

### Pricing (Phase 1)

| Tier | Price | Calls/month | Agents |
|------|-------|------------|--------|
| Free | $0 | 100 | FORGE only |
| Pro | $49/mo | 10,000 | All 5 |
| Team | $199/mo | 50,000 | All 5 + custom fine-tune |

### Revenue target: $490/mo (10 Pro users)

---

## Phase 2 — AI University Beta (Month 2)

**Goal:** 50 enrolled users, measurable completion rates, first testimonials.

### Core Features

- **Course catalogue** — 5 agent specialisation courses (ORACLE, FORGE, CODEX, SENTINEL, NEXUS).
- **Professor agent** — CODEX or ORACLE running as the teaching interface.
- **Progress tracking** — SQLite store: user_id, module_id, mastery_score, last_seen.
- **Certification** — PDF certificate on 80%+ mastery, stored in Supabase or S3.

### Steps

1. Build `university_server.py` — FastAPI endpoints: enroll, lesson, submit-answer, progress.
2. Extend SwarmBus professor mode: `MsgType.TEACH` routes to the appropriate agent.
3. Add spaced-repetition scheduler (SM-2 variant) — runs as a background task.
4. Write 5 course outlines using `sovereign_trainer_v5.py --domain university --generate-only`.
5. Beta invite to existing Pro users + Developer Discord.

### Revenue target: $2,450/mo (50 Pro users)

---

## Phase 3 — Agent Marketplace (Month 3)

**Goal:** $5,000 MRR. External agents listed, first marketplace transaction.

### Features

- **Listing schema** — name, description, domain, version, HF repo, system prompt, pricing.
- **One-click deploy** — pull LoRA from HF, slot into SwarmBus, expose as API endpoint.
- **Quality score** — rubric: response coherence (0–40) + domain accuracy (0–40) + safety (0–20).
- **Marketplace billing** — 20% platform fee on API calls through marketplace agents.
- **Developer portal** — list your fine-tuned agent, set per-call price, track revenue.

### Revenue target: $5,000 MRR (80 Pro + 10 Team + marketplace commissions)

---

## Phase 4 — Enterprise Contracts (Months 4–6)

**Goal:** 3 signed contracts at $5K–$25K each. Total ARR > $100K.

### Target Segments

| Segment | Pain point | Offer | Price |
|---------|-----------|-------|-------|
| Regulated fintech | Compliance-aware AI | Private deployment + SENTINEL fine-tune | $15K setup + $2K/mo |
| EdTech platforms | Scalable tutoring | AI University white-label | $10K setup + $1.5K/mo |
| Security consultancies | AI-assisted pen testing | SENTINEL + CODEX custom training | $25K/domain |

### Outreach strategy
1. 10 cold emails/day via Apollo.io — target CTOs at 50–200 person companies.
2. 2 conference talks: DEF CON AI Village (security angle), LearnX (EdTech angle).
3. 5 case studies from Phase 2 beta users — convert to testimonials + LinkedIn posts.

---

## Phase 5 — Scale (Month 7+)

**Hiring trigger:** $10K MRR sustained for 2 months.

| Role | Trigger MRR | Focus |
|------|-------------|-------|
| Part-time customer success | $5K | Onboarding + retention |
| Full-time engineer | $15K | Marketplace infrastructure |
| Sales / BD | $25K | Enterprise pipeline |

**Infrastructure:** Migrate from single VPS → Kubernetes on Hetzner (50% cheaper than AWS).  
**Model upgrades:** Qwen2.5-32B or Llama 3.1-70B via RunPod on-demand for premium tier.

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| OpenAI releases competing product | High | Medium | Emphasise private deployment + customisation moat |
| VRAM constraints limit model quality | Medium | Medium | RunPod on-demand for generation; local for fine-tune |
| Churn before product-market fit | Medium | High | Monthly check-ins, direct Discord engagement, iterate on ICP |
| HuggingFace policy change on free hosting | Low | Medium | Mirror datasets on S3, self-host inference |
| Regulatory pressure on AI training data | Low | High | Use only permissive-license sources, document provenance |
