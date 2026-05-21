"""
multiturn_gen.py — Generate multi-turn conversation training data for Avery.

Creates realistic back-and-forth dialogues where users iteratively refine
strategy questions and Avery responds in KAIROS framework style.
Each example = OpenAI messages format with 2-4 turns.

Output: data/multiturn_dataset.jsonl

Run:
  python multiturn_gen.py --pairs 200
  python multiturn_gen.py --pairs 200 --append
"""
import argparse, json, os, sys, random, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT   = Path(__file__).parent
DATA   = ROOT / "data"
OUTPUT = DATA / "multiturn_dataset.jsonl"

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"   # fast + cheap for bulk generation


def _load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

_load_env()

SYSTEM = (
    "You are Avery, the sovereign business strategist for SovereignNation — "
    "a fixed-cost AI platform built for lower and middle class families, "
    "children's education, and affordable connectivity. "
    "You reason through strategy using the KAIROS framework: "
    "K=Kickoff, A=Alignment, I=Implementation, R=Refinement, O=Optimization, S=Scaling. "
    "Be direct, structured, and actionable. Keep responses focused and concrete."
)

# Seed scenarios — each generates a 2-4 turn conversation
SEED_SCENARIOS = [
    # Format: (opening_question, followup_questions...)
    (
        "We need a go-to-market strategy for SovereignNation's $29/month family tier targeting rural communities.",
        ["Can you give me more detail on the Implementation phase?",
         "What KPIs should we track during the Optimization phase?"],
    ),
    (
        "SovereignNation is at 15,000 subscribers and growth has stalled. What's the unlock?",
        ["Which of these tactics would you prioritize first with limited budget?",
         "How do we measure if these are working in the first 30 days?"],
    ),
    (
        "We want to partner with school districts. How should we approach this?",
        ["What if the district wants a pilot before committing?",
         "How do we handle procurement bureaucracy in large districts?"],
    ),
    (
        "Design a pricing strategy that stays affordable but covers infrastructure costs at scale.",
        ["How do we handle users who can't afford even the lowest tier?",
         "What's the break-even calculation for the $29 tier?"],
    ),
    (
        "We need to cut costs by 30% without degrading service quality.",
        ["Where do we start — infrastructure, team, or vendor contracts?",
         "How do we communicate cuts to subscribers without losing trust?"],
    ),
    (
        "A major EdTech company just offered to acquire SovereignNation. How do we respond?",
        ["What are the red flags that tell us to reject outright?",
         "If we negotiate, what terms are non-negotiable for our mission?"],
    ),
    (
        "Build a community moderator program for SovereignNation's local chapters.",
        ["How do we prevent moderator burnout in volunteer programs?",
         "What tools and authority do moderators need to be effective?"],
    ),
    (
        "We have 6 months of runway left. What's the survival plan?",
        ["Which revenue streams can generate cash fastest?",
         "What's the minimum viable operation we cut to while fundraising?"],
    ),
    (
        "Design SovereignNation's AI model update strategy — how often and how do we deploy improvements?",
        ["How do we test model updates without disrupting live subscribers?",
         "What's the rollback strategy if an update degrades quality?"],
    ),
    (
        "We want to build a data flywheel where usage improves our AI quality automatically.",
        ["How do we collect training signal without violating user privacy?",
         "What's the feedback loop timeline from data to improved model?"],
    ),
    (
        "SovereignNation needs to handle a 10x traffic spike during back-to-school season.",
        ["Should we pre-scale or auto-scale? What's the cost tradeoff?",
         "How do we communicate degraded performance to users if it happens?"],
    ),
    (
        "Design a multi-language support rollout starting with Spanish.",
        ["How do we ensure cultural accuracy not just translation?",
         "What's the priority order for additional languages after Spanish?"],
    ),
    (
        "A government agency wants to use SovereignNation for housing voucher recipients. Plan the integration.",
        ["How do we handle government procurement timelines vs our runway?",
         "What data privacy requirements will we need to meet?"],
    ),
    (
        "Build a churn prevention strategy. We're losing 8% of subscribers monthly.",
        ["How do we identify at-risk subscribers before they cancel?",
         "What's the cheapest intervention that actually retains people?"],
    ),
    (
        "We want to build a peer-to-peer skills economy inside SovereignNation. How do we start?",
        ["How do we prevent exploitation of vulnerable users in a gig economy?",
         "What's the minimum viable version we can test in 60 days?"],
    ),
    (
        "SovereignNation's AI tutor is getting poor reviews for math explanations. Fix it.",
        ["Should we fine-tune the model or fix the prompting first?",
         "How do we measure improvement — what's our success metric?"],
    ),
    (
        "Design a strategy for SovereignNation to serve formerly incarcerated individuals re-entering society.",
        ["What are the unique digital barriers this population faces?",
         "How do we partner with reentry programs and halfway houses?"],
    ),
    (
        "We need to build a crisis communications plan for SovereignNation.",
        ["What are the top 3 crisis scenarios we should plan for?",
         "Who speaks for SovereignNation in a public crisis — founder or comms team?"],
    ),
    (
        "Build an advisory board strategy for SovereignNation in its first year.",
        ["What skills gaps does our current team have that advisors should fill?",
         "How do we compensate advisors without cash when we're pre-revenue?"],
    ),
    (
        "Design SovereignNation's content moderation policy for community discussions.",
        ["How do we handle political speech that isn't hate speech but is divisive?",
         "What's our appeals process for moderation decisions?"],
    ),
    # Agent-specific multi-turn scenarios
    (
        "Walk me through how ORACLE would retrieve and synthesize context about a subscriber's 6-month history.",
        ["What happens if the memory is incomplete or contradictory?",
         "How does ORACLE hand off context to FORGE for code generation?"],
    ),
    (
        "Explain how FORGE generates a production FastAPI endpoint from scratch.",
        ["What does FORGE do when requirements are ambiguous?",
         "How does FORGE coordinate with CODEX for the security review?"],
    ),
    (
        "How does SENTINEL detect and respond to a prompt injection attack in real time?",
        ["What's the escalation path when SENTINEL finds a critical threat?",
         "How do we tune SENTINEL's sensitivity without too many false positives?"],
    ),
    (
        "Describe NEXUS's workflow for orchestrating a 3-agent collaborative task.",
        ["How does NEXUS handle it when one agent fails partway through?",
         "What's NEXUS's rollback strategy for a failed GitHub push?"],
    ),
    (
        "How does Avery use the KAIROS framework for a completely novel scenario it hasn't seen before?",
        ["What phase does Avery spend the most time on and why?",
         "How does Avery adapt KAIROS when resources are severely constrained?"],
    ),
]


def _generate_conversation(client, scenario: tuple) -> dict | None:
    """Generate a multi-turn conversation for a seed scenario."""
    import anthropic

    opening = scenario[0]
    followups = scenario[1]  # list of followup strings
    # Randomly use 1 or 2 followups
    num_followups = random.randint(1, min(2, len(followups)))
    selected_followups = followups[:num_followups]

    messages = []
    full_conversation = []

    try:
        # Turn 1: opening
        messages.append({"role": "user", "content": opening})
        resp1 = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1200,
            system=SYSTEM,
            messages=messages,
        )
        reply1 = resp1.content[0].text.strip()
        if len(reply1) < 200:
            return None
        messages.append({"role": "assistant", "content": reply1})
        full_conversation = [
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": opening},
            {"role": "assistant", "content": reply1},
        ]

        # Subsequent turns
        for followup in selected_followups:
            messages.append({"role": "user", "content": followup})
            resp_n = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=800,
                system=SYSTEM,
                messages=messages,
            )
            reply_n = resp_n.content[0].text.strip()
            if len(reply_n) < 100:
                break
            messages.append({"role": "assistant", "content": reply_n})
            full_conversation.append({"role": "user",      "content": followup})
            full_conversation.append({"role": "assistant", "content": reply_n})

        return {
            "messages": full_conversation,
            "source": "multiturn_anthropic",
            "turns": len([m for m in full_conversation if m["role"] == "user"]),
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs",   type=int, default=200)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--append",  action="store_true")
    args = ap.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set"); sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("ERROR: pip install anthropic"); sys.exit(1)

    client = anthropic.Anthropic(api_key=anthropic_key)

    # Build instruction list by cycling through seed scenarios
    scenarios = []
    while len(scenarios) < args.pairs:
        shuffled = list(SEED_SCENARIOS)
        random.shuffle(shuffled)
        scenarios.extend(shuffled)
    scenarios = scenarios[:args.pairs]

    print(f"\n{'='*58}")
    print("  MULTI-TURN CONVERSATION GENERATOR")
    print(f"{'='*58}")
    print(f"  Target   : {args.pairs} conversations")
    print(f"  Workers  : {args.workers}")
    print(f"  Model    : {ANTHROPIC_MODEL}")
    print(f"  Output   : {OUTPUT}")
    print()

    DATA.mkdir(exist_ok=True)
    file_mode = "a" if args.append else "w"
    generated = 0
    failed = 0
    _lock = threading.Lock()

    def _worker(idx_scenario):
        idx, scenario = idx_scenario
        return idx, _generate_conversation(client, scenario)

    with open(OUTPUT, file_mode, encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_worker, (i, s)): i for i, s in enumerate(scenarios)}
            for future in as_completed(futures):
                idx, result = future.result()
                if result:
                    with _lock:
                        f.write(json.dumps(result, ensure_ascii=False) + "\n")
                        f.flush()
                        generated += 1
                    print(f"  [{idx+1}] OK ({result['turns']} turns) — {generated} total")
                else:
                    with _lock:
                        failed += 1
                    print(f"  [{idx+1}] SKIP")

    print(f"\n{'='*58}")
    print(f"  Done: {generated} conversations, {failed} failed")
    print(f"  Output: {OUTPUT}")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    main()
