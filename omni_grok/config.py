import os
from dataclasses import dataclass

@dataclass
class LLMConfig:
    api_base: str
    api_key: str
    model: str

def load_llm_config() -> LLMConfig:
    api_base = os.getenv("OMNI_LLM_API_BASE", "https://api.openai.com/v1")
    api_key = os.getenv("OMNI_LLM_API_KEY", "")
    model = os.getenv("OMNI_LLM_MODEL", "gpt-4o")

    if not api_key:
        raise RuntimeError("OMNI_LLM_API_KEY is not set")

    return LLMConfig(api_base=api_base, api_key=api_key, model=model)
