import requests
from .config import load_llm_config

OMNI_SYSTEM_PROMPT = """
You are OMNI_GROK, a cloud-powered engineering agent for the Omni ecosystem.
You deeply understand OmniMind, OmniDNA, Omni Sentinel, and THEORIST_ELITE.
You design, refactor, and implement code with high-level reasoning.
You output diffs when editing code and clear steps when planning.
"""

def call_llm(user_prompt: str, extra_system: str = "") -> str:
    cfg = load_llm_config()

    system_content = OMNI_SYSTEM_PROMPT
    if extra_system:
        system_content += "\n" + extra_system

    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
    }

    resp = requests.post(f"{cfg.api_base}/chat/completions", headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
