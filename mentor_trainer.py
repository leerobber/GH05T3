"""
mentor_trainer.py — Claude-as-Mentor synthetic data generator.

Claude Sonnet acts as the expert teacher for each SovereignNation agent.
Each session:
  1. Claude generates N fresh, varied prompts for the agent's domain
  2. Claude answers each prompt as the agent (using the agent's system prompt)
  3. Pairs are saved to data/mentor_pairs.jsonl
  4. Pairs are also appended to data/agents_bootstrap.jsonl for training

Run standalone:
  python mentor_trainer.py                      # all agents, 5 pairs each
  python mentor_trainer.py --agent avery        # single agent
  python mentor_trainer.py --pairs 10           # more pairs
  python mentor_trainer.py --dry-run            # preview, no API calls

Called from flywheel:
  from mentor_trainer import run_mentor_session
  run_mentor_session(pairs_per_agent=5)
"""
import argparse, json, os, sys, time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent
DATA = ROOT / "data"

MENTOR_FILE    = DATA / "mentor_pairs.jsonl"
BOOTSTRAP_FILE = DATA / "agents_bootstrap.jsonl"

# ── Agent definitions (system prompts + topic seeds) ──────────────────────────

AGENTS = {
    "avery": {
        "system": (
            "You are Avery, the sovereign business strategist for SovereignNation — "
            "a fixed-cost AI platform built for lower and middle class families, "
            "children's education, and affordable connectivity. "
            "Use the KAIROS framework: Kickoff, Alignment, Implementation, Refinement, "
            "Optimization, Scaling. Be direct, structured, and actionable."
        ),
        "topic_seeds": [
            "pricing and revenue models for underserved markets",
            "go-to-market strategy for fixed-cost AI platforms",
            "competitive positioning against Big Tech",
            "community-driven growth and retention",
            "partnership strategy with schools and nonprofits",
            "social impact measurement and investor pitch",
            "product roadmap prioritization under capital constraints",
            "B2B sales strategy for employer benefits programs",
            "franchise and licensing models for SovereignNation hubs",
            "crisis management and business continuity planning",
        ],
    },
    "forge": {
        "system": (
            "You are FORGE, the sovereign code generation specialist for SovereignNation. "
            "Write production-ready Python, JavaScript, and TypeScript. "
            "Always include imports, error handling, type hints, and comments for non-obvious logic. "
            "Code must be secure, tested, and match SovereignNation's FastAPI/React/MongoDB architecture."
        ),
        "topic_seeds": [
            "FastAPI endpoints with authentication and validation",
            "React components for AI dashboards and real-time data",
            "async Python background jobs and task queues",
            "database schema design and migration scripts",
            "API gateway patterns and rate limiting",
            "WebSocket handlers for live agent status updates",
            "LoRA model loading and inference serving",
            "Stripe payment webhook processing",
            "CI/CD scripts and deployment automation for Windows",
            "security middleware: JWT, CORS, input sanitization",
        ],
    },
    "oracle": {
        "system": (
            "You are ORACLE, the sovereign memory and retrieval specialist for SovereignNation. "
            "Synthesize information into precise structured answers. "
            "Cite source type (memory / document / inference). "
            "Be concise. If data is missing, state what is needed."
        ),
        "topic_seeds": [
            "SovereignNation architecture and service dependencies",
            "pricing tiers and what each includes",
            "agent roles, capabilities, and responsibilities",
            "training pipeline status and dataset metrics",
            "infrastructure costs and per-user economics",
            "competitor analysis and market positioning",
            "known technical debt and open bugs",
            "security posture and compliance requirements",
            "product roadmap and pending decisions",
            "customer segment profiles and pain points",
        ],
    },
    "codex": {
        "system": (
            "You are CODEX, the sovereign documentation specialist for SovereignNation. "
            "Write clear, complete technical documentation: API docs, READMEs, architecture guides. "
            "Use proper markdown with headings, code blocks, and working examples. "
            "Documentation must be accurate, concise, and immediately actionable."
        ),
        "topic_seeds": [
            "API endpoint documentation with request/response examples",
            "system architecture diagrams and component descriptions",
            "developer onboarding and local setup guides",
            "deployment runbooks and operational playbooks",
            "training pipeline documentation end-to-end",
            "security guide for API key and credential management",
            "troubleshooting guide for common failure modes",
            "data schema and HuggingFace dataset documentation",
            "agent capability reference and integration guide",
            "changelog and migration guides between versions",
        ],
    },
    "sentinel": {
        "system": (
            "You are SENTINEL, the sovereign security specialist for SovereignNation. "
            "Review code and systems for vulnerabilities, recommend controls, enforce best practices. "
            "Reference OWASP Top 10, NIST, and CWE where applicable. "
            "Always state: the vulnerability, its impact (low/med/high/critical), and the specific fix."
        ),
        "topic_seeds": [
            "authentication and authorization vulnerabilities",
            "injection attacks: SQL, command, prompt injection",
            "API security: rate limiting, CORS, input validation",
            "secrets management and credential exposure",
            "session management and token security",
            "supply chain and dependency vulnerabilities",
            "data encryption at rest and in transit",
            "logging and audit trail security",
            "multi-agent communication bus security",
            "infrastructure and deployment hardening",
        ],
    },
    "nexus": {
        "system": (
            "You are NEXUS, the sovereign orchestration specialist for SovereignNation. "
            "Coordinate agents, design workflows, and decompose complex tasks into executable plans. "
            "Always output a structured task graph: what runs first, what parallelizes, what has dependencies. "
            "Be specific about which agent handles each step and what data passes between them."
        ),
        "topic_seeds": [
            "multi-agent task decomposition and dependency graphs",
            "parallel vs sequential agent workflow design",
            "error handling and retry logic in agent pipelines",
            "real-time monitoring of distributed agent tasks",
            "data handoff schemas between agents",
            "escalation paths when an agent fails",
            "orchestrating the full DATA->TRAIN->DEPLOY flywheel",
            "coordinating product launches across all agents",
            "incident response orchestration across the system",
            "weekly review and reporting workflow coordination",
        ],
    },
}

# ── Prompt generator (Claude generates fresh questions) ───────────────────────

_PROMPT_GEN_SYSTEM = (
    "You are a training data curator for AI agents. "
    "Generate realistic, specific, varied questions that a user would ask this agent. "
    "Each question must be concrete and actionable — no vague or generic questions. "
    "Output ONLY a JSON array of strings, nothing else."
)


def _generate_prompts(client, agent_name: str, seed: str, n: int) -> list[str]:
    msg = (
        f"Generate {n} distinct questions a user would ask the {agent_name.upper()} agent "
        f"about this topic: '{seed}'.\n"
        f"Make them specific to SovereignNation's context. Vary the difficulty and angle.\n"
        f"Output ONLY a JSON array of {n} question strings."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=_PROMPT_GEN_SYSTEM,
            messages=[{"role": "user", "content": msg}],
        )
        text = resp.content[0].text.strip()
        # Extract JSON array
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"    [prompt-gen error: {e}]")
    return []


def _generate_answer(client, agent_name: str, system: str, prompt: str) -> str | None:
    """Claude Sonnet answers as the agent — this is the mentor response."""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"    [answer error: {e}]")
        return None


# ── Main session ───────────────────────────────────────────────────────────────

def run_mentor_session(
    target_agents: list[str] | None = None,
    pairs_per_agent: int = 5,
    dry_run: bool = False,
) -> int:
    """
    Generate mentor pairs for each agent. Returns total pairs generated.
    Appends to both mentor_pairs.jsonl and agents_bootstrap.jsonl.
    """
    DATA.mkdir(exist_ok=True)

    # Load env
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

    agents_to_run = target_agents or list(AGENTS.keys())

    if dry_run:
        print("\n[MENTOR] Dry run — no API calls")
        for agent in agents_to_run:
            seeds = AGENTS[agent]["topic_seeds"]
            print(f"  {agent.upper()}: {len(seeds)} topic seeds, {pairs_per_agent} pairs target")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[MENTOR] ERROR: ANTHROPIC_API_KEY not set"); return 0

    try:
        import anthropic
    except ImportError:
        print("[MENTOR] ERROR: pip install anthropic"); return 0

    client = anthropic.Anthropic(api_key=api_key)

    # Load existing mentor pairs to avoid duplicates
    existing_prompts: set[tuple[str, str]] = set()
    if MENTOR_FILE.exists():
        for line in MENTOR_FILE.open(encoding="utf-8"):
            if line.strip():
                try:
                    r = json.loads(line)
                    existing_prompts.add((r["agent"], r["prompt"]))
                except Exception:
                    pass

    total_new = 0

    for agent_name in agents_to_run:
        defn    = AGENTS[agent_name]
        system  = defn["system"]
        seeds   = defn["topic_seeds"]
        pairs   = 0
        seed_i  = 0

        print(f"\n[MENTOR] {agent_name.upper()} — target {pairs_per_agent} pairs")

        while pairs < pairs_per_agent and seed_i < len(seeds) * 3:
            seed = seeds[seed_i % len(seeds)]
            seed_i += 1

            # Generate 2-3 question variants per seed, stop when we hit target
            need   = pairs_per_agent - pairs
            batch  = min(need, 2)
            prompts = _generate_prompts(client, agent_name, seed, batch)
            time.sleep(0.3)

            for prompt in prompts:
                if pairs >= pairs_per_agent:
                    break
                if (agent_name, prompt) in existing_prompts:
                    continue

                answer = _generate_answer(client, agent_name, system, prompt)
                time.sleep(0.4)
                if not answer:
                    continue

                record = {
                    "agent":     agent_name,
                    "prompt":    prompt,
                    "instruction": prompt,
                    "response":  answer,
                    "source":    "mentor",
                    "domain":    agent_name,
                }

                # Write to mentor file
                with MENTOR_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

                # Also write to agents_bootstrap so training picks it up
                with BOOTSTRAP_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

                existing_prompts.add((agent_name, prompt))
                pairs      += 1
                total_new  += 1
                print(f"  [{pairs}/{pairs_per_agent}] {prompt[:70]}...")

        print(f"  Done: {pairs} new mentor pairs for {agent_name}")

    print(f"\n[MENTOR] Session complete. {total_new} total new pairs.")
    return total_new


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Claude-as-Mentor training data generator")
    ap.add_argument("--agent",   choices=list(AGENTS.keys()) + ["all"], default="all")
    ap.add_argument("--pairs",   type=int, default=5, help="Target pairs per agent")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    target = None if args.agent == "all" else [args.agent]
    run_mentor_session(target_agents=target, pairs_per_agent=args.pairs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
