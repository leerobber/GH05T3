from .llm_client import call_llm
from .tools import read_file, list_files, run_command

def ask_omni(prompt: str) -> str:
    return call_llm(prompt)

def explain_file(path: str) -> str:
    content = read_file(path)
    prompt = f"Explain this file in the context of the Omni ecosystem:\n\n{content}"
    return call_llm(prompt)

def plan_task(task: str) -> str:
    prompt = f"Plan this task for the Omni project:\n{task}"
    return call_llm(prompt)

def propose_diff(path: str, task: str) -> str:
    content = read_file(path)
    prompt = f"File: {path}\n\nCurrent content:\n{content}\n\nTask:\n{task}\n\nReturn ONLY a unified diff."
    return call_llm(prompt)

def omni_context_summary() -> str:
    files = list_files()
    prompt = f"Here are project files:\n{files}\n\nSummarize architecture and next steps."
    return call_llm(prompt)

def suggest_commands(task: str) -> str:
    prompt = f"Suggest shell commands for:\n{task}"
    return call_llm(prompt)

def dry_run_command(cmd: str) -> str:
    return run_command(cmd)
