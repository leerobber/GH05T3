import torch
from gh05t3_train.config import DEVICE
from gh05t3_train.model_core import GH05T3MiniHybrid
from gh05t3_train.run import main as train_main

import math
import traceback


class GH05T3Memory:
    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        self.items = []

    def add(self, user_text: str, reasoning: str, answer: str):
        self.items.append((user_text, reasoning, answer))
        if len(self.items) > self.max_items:
            self.items.pop(0)

    def build_context(self, user_text: str) -> str:
        lines = []
        if self.items:
            lines.append("MEMORY:")
            for u, r, a in self.items[-5:]:
                lines.append(f"- USER: {u}")
                lines.append(f"  REASONING: {r}")
                lines.append(f"  ANSWER: {a}")
            lines.append("")
        lines.append("QUERY:")
        lines.append(user_text)
        return "\n".join(lines)


def tool_calculator(expr: str) -> str:
    try:
        result = eval(expr, {"__builtins__": {}}, {"math": math})
        return str(result)
    except Exception as e:
        return f"Calculator error: {e}"


def tool_python(code: str) -> str:
    try:
        local_env = {}
        exec(code, {"math": math}, local_env)
        return str(local_env) if local_env else "Code executed."
    except Exception as e:
        return f"Python error: {e}\n{traceback.format_exc()}"


def route_tool(command: str) -> str:
    if not command.startswith("TOOL:"):
        return "Invalid tool command."

    try:
        _, rest = command.split("TOOL:", 1)
        rest = rest.strip()
        tool_name, arg = rest.split("|", 1)
        tool_name = tool_name.strip().lower()
        arg = arg.strip()
    except ValueError:
        return "Malformed tool command."

    if tool_name == "calculator":
        return tool_calculator(arg)
    elif tool_name == "python":
        return tool_python(arg)
    else:
        return f"Unknown tool: {tool_name}"


class GH05T3Agent:
    def __init__(self, model: GH05T3MiniHybrid, tokenizer):
        self.model = model.to(DEVICE)
        self.tokenizer = tokenizer
        self.memory = GH05T3Memory()

    def _generate_token(self, logits):
        probs = torch.softmax(logits, dim=-1)
        next_id = torch.argmax(probs, dim=-1).item()
        return self.tokenizer.decode([next_id])

    def generate(self, user_text: str, max_len: int = 128):
        context_text = self.memory.build_context(user_text)

        tokens = self.tokenizer.encode(context_text, add_special_tokens=False)
        tokens = tokens[:max_len]
        token_ids = torch.tensor(tokens, dtype=torch.long, device=DEVICE).unsqueeze(0)

        raw_texts = [context_text]

        with torch.no_grad():
            logits_answer, logits_reason = self.model(token_ids, raw_texts)

        reasoning_text = self._generate_token(logits_reason)

        tool_result = None
        if reasoning_text.strip().startswith("TOOL:"):
            tool_result = route_tool(reasoning_text.strip())

        if tool_result:
            enhanced = context_text + f"\nTOOL RESULT: {tool_result}"
            tokens = self.tokenizer.encode(enhanced, add_special_tokens=False)
            tokens = tokens[:max_len]
            token_ids = torch.tensor(tokens, dtype=torch.long, device=DEVICE).unsqueeze(0)
            raw_texts = [enhanced]

            with torch.no_grad():
                logits_answer, _ = self.model(token_ids, raw_texts)

        answer_text = self._generate_token(logits_answer)

        self.memory.add(user_text, reasoning_text, answer_text)

        if tool_result:
            return f"REASONING: {reasoning_text}\nTOOL RESULT: {tool_result}\nANSWER: {answer_text}"
        else:
            return f"REASONING: {reasoning_text}\nANSWER: {answer_text}"


def build_agent_from_checkpoint():
    model, tokenizer = train_main()
    return GH05T3Agent(model, tokenizer)


if __name__ == "__main__":
    agent = build_agent_from_checkpoint()
    print("=== GH05T3 Agent (Memory + Tools + Reasoning Head) ===")
    print("Type 'exit' to quit.\n")

    while True:
        user = input("You: ").strip()
        if user.lower() == "exit":
            break
        reply = agent.generate(user)
        print(f"GH05T3:\n{reply}\n")
