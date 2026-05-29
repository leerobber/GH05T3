"""
skills_manager.py — Hermes-style skills system for SovereignNation pipeline agents.

Skills are markdown files in sovereignnation/skills/{agent}/*.md
Each skill = one domain of accumulated knowledge the agent has learned.

Progressive disclosure:
  - System prompt gets skill names + 1-line descriptions only (~100 tokens overhead)
  - Full content only loaded when agent decides it's relevant
  - Agent can create/update/delete its own skills via the /reflect endpoint

Compatible with agentskills.io open standard format.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("skills_manager")

SKILLS_ROOT = Path(__file__).parent / "skills"


def _extract_description(content: str) -> str:
    """Pull the first meaningful line from a skill file as its description."""
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---") and not line.startswith("<!--"):
            return line[:120]
    # fallback: use first heading
    for line in content.strip().split("\n"):
        if line.startswith("# "):
            return line[2:120]
    return "General knowledge"


def load_skills_index(agent: str) -> list:
    """
    Return [{name, description}] for a given agent.
    Used to inject skill titles into the system prompt.
    """
    agent_dir = SKILLS_ROOT / agent
    if not agent_dir.exists():
        return []

    skills = []
    for f in sorted(agent_dir.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            desc = _extract_description(content)
            skills.append({"name": f.stem, "description": desc})
        except Exception as e:
            log.warning(f"Could not read skill {f}: {e}")
    return skills


def load_skill(agent: str, name: str) -> str:
    """Load full content of a specific skill."""
    path = SKILLS_ROOT / agent / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"Skill '{name}' not found for agent '{agent}'."


def save_skill(agent: str, name: str, content: str) -> bool:
    """
    Write a skill file. Creates the agent directory if needed.
    Called by the post-task reflection loop when a new skill is learned.
    """
    agent_dir = SKILLS_ROOT / agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    log.info(f"Skill saved: {agent}/{name} ({len(content)} chars)")
    return True


def patch_skill(agent: str, name: str, old_string: str, new_string: str) -> bool:
    """
    Targeted patch to an existing skill (preferred over full rewrite — more token efficient).
    """
    path = SKILLS_ROOT / agent / f"{name}.md"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    if old_string not in content:
        return False
    path.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
    log.info(f"Skill patched: {agent}/{name}")
    return True


def delete_skill(agent: str, name: str) -> bool:
    """Delete a skill file."""
    path = SKILLS_ROOT / agent / f"{name}.md"
    if path.exists():
        path.unlink()
        log.info(f"Skill deleted: {agent}/{name}")
        return True
    return False


def list_all_skills() -> dict:
    """Return {agent: [skills]} for all agents — used by /health endpoint."""
    result = {}
    if not SKILLS_ROOT.exists():
        return result
    for agent_dir in sorted(SKILLS_ROOT.iterdir()):
        if agent_dir.is_dir():
            result[agent_dir.name] = load_skills_index(agent_dir.name)
    return result


def inject_skills_into_prompt(agent: str, system: str) -> str:
    """
    Append the skills index to the system prompt.
    Only adds skill names + 1-line descriptions (low token cost).
    The agent is instructed to mentally load relevant skills as needed.
    """
    skills = load_skills_index(agent)
    if not skills:
        return system

    skills_block = "\n\n## Your Accumulated Skills (procedural memory):\n"
    for s in skills:
        skills_block += f"- **{s['name']}**: {s['description']}\n"
    skills_block += (
        "\nThese skills represent patterns you've learned from past tasks. "
        "Apply relevant skills automatically when answering. "
        "If you discover something worth preserving, note it — it will be saved.\n"
    )
    return system + skills_block


def build_reflection_prompt(agent: str, task: str, response: str) -> str:
    """
    Build the prompt used to ask an agent whether it learned something worth saving.
    Aggressive version: biased toward creating skills, not skipping.
    """
    existing = [s["name"] for s in load_skills_index(agent)]
    existing_str = ", ".join(existing) if existing else "none yet"

    return f"""Extract a reusable skill from this completed task.

AGENT: {agent.upper()}
TASK: {task[:400]}
RESPONSE SUMMARY: {response[:500]}
EXISTING SKILLS (do not duplicate): {existing_str}

A skill is a pattern, framework, threshold, or decision rule that would help on FUTURE similar tasks.
Examples of good skills: "cpa_roi_formula", "prospect_qualification_thresholds", "pricing_decision_framework"
Examples of bad skills: "how_to_answer_this_specific_question"

You MUST output valid JSON. Choose one:

If a reusable pattern exists (PREFERRED — be generous, create skills liberally):
{{"action": "create", "name": "short_snake_case", "content": "One paragraph describing the pattern, key numbers, and when to apply it."}}

If an existing skill should be updated with new info:
{{"action": "patch", "name": "existing_skill_name", "old_string": "text to replace", "new_string": "better text"}}

If truly nothing is reusable (rare — only for pure calculations with no generalizable rule):
{{"action": "none"}}

Output JSON only. No markdown. No explanation. Start with {{"""
