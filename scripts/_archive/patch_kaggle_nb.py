"""Patch kaggle_push/kernel.ipynb — fix BF16/FP16 and memory settings."""
import json
from pathlib import Path

nb_path = Path(__file__).parent / "kaggle_push" / "kernel.ipynb"
nb = json.loads(nb_path.read_text(encoding="utf-8"))

def src(cell):
    s = cell["source"]
    return "".join(s) if isinstance(s, list) else s

def set_src(cell, text):
    lines = text.split("\n")
    cell["source"] = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])

# Find training cell
for i, cell in enumerate(nb["cells"]):
    if "USE_BF16" in src(cell) and "trainer.train()" in src(cell):
        training_idx = i
        break

print(f"Patching training cell at index {training_idx}")

NEW_TRAINING_CELL = '''# ── 7. Format + train ─────────────────────────────────────────────────────────
import torch
from transformers import TrainingArguments

# T4 = FP16 only. A100/H100 = BF16. Detect properly.
USE_BF16 = (BACKEND == 'cuda') and torch.cuda.is_bf16_supported()
USE_FP16 = (BACKEND == 'cuda') and not USE_BF16
print(f'Precision: {"BF16" if USE_BF16 else "FP16" if USE_FP16 else "FP32"}')

def _wrap(goal):
    return (f'<|im_start|>system\\n{SYSTEM}<|im_end|>\\n'
            f'<|im_start|>user\\n{goal}<|im_end|>\\n'
            f'<|im_start|>assistant\\n')

if MODE == 'sft':
    from trl import SFTTrainer

    def fmt(row):
        g = str(row.get('instruction') or row.get('goal') or row.get('prompt') or '')
        r = str(row.get('response') or row.get('chosen') or '')
        return {'text': _wrap(g) + r + '<|im_end|>'}

    ds_fmt  = ds.map(fmt, remove_columns=ds.column_names)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=ds_fmt, dataset_text_field='text',
        max_seq_length=1024,
        args=TrainingArguments(
            per_device_train_batch_size=2, gradient_accumulation_steps=4,
            num_train_epochs=EPOCHS, learning_rate=2e-4,
            bf16=USE_BF16, fp16=USE_FP16, logging_steps=10,
            output_dir=OUTPUT_DIR, warmup_ratio=0.1,
            lr_scheduler_type='cosine', save_strategy='epoch',
            report_to='none', optim='adamw_8bit',
        ),
    )

elif MODE == 'orpo':
    from trl import ORPOTrainer, ORPOConfig

    def fmt_orpo(row):
        g = str(row.get('goal') or row.get('instruction') or '')
        p = str(row.get('prompt') or f'GOAL: {g}\\n\\nProvide a detailed sovereign response:')
        return {
            'prompt':   _wrap(p),
            'chosen':   str(row['chosen']) + '<|im_end|>',
            'rejected': str(row['rejected']) + '<|im_end|>',
        }

    ds_fmt  = ds.map(fmt_orpo, remove_columns=ds.column_names)
    trainer = ORPOTrainer(
        model=model, tokenizer=tokenizer, train_dataset=ds_fmt,
        args=ORPOConfig(
            max_length=1024, max_prompt_length=384, beta=0.1,
            per_device_train_batch_size=1, gradient_accumulation_steps=4,
            num_train_epochs=EPOCHS, learning_rate=8e-6,
            bf16=USE_BF16, fp16=USE_FP16, logging_steps=10,
            output_dir=OUTPUT_DIR, warmup_ratio=0.1,
            lr_scheduler_type='cosine', save_strategy='epoch',
            report_to='none', optim='adamw_8bit',
        ),
    )

elif MODE == 'dpo':
    from trl import DPOTrainer, DPOConfig

    def fmt_dpo(row):
        g = str(row.get('goal') or row.get('instruction') or '')
        p = str(row.get('prompt') or f'GOAL: {g}\\n\\nProvide a detailed sovereign response:')
        return {
            'prompt':   _wrap(p),
            'chosen':   str(row['chosen']) + '<|im_end|>',
            'rejected': str(row['rejected']) + '<|im_end|>',
        }

    ds_fmt  = ds.map(fmt_dpo, remove_columns=ds.column_names)
    trainer = DPOTrainer(
        model=model, ref_model=None, tokenizer=tokenizer, train_dataset=ds_fmt,
        args=DPOConfig(
            max_length=1024, max_prompt_length=384, beta=0.1,
            per_device_train_batch_size=1, gradient_accumulation_steps=4,
            num_train_epochs=EPOCHS, learning_rate=5e-6,
            bf16=USE_BF16, fp16=USE_FP16, logging_steps=10,
            output_dir=OUTPUT_DIR, warmup_ratio=0.1,
            lr_scheduler_type='cosine', save_strategy='epoch',
            report_to='none', optim='adamw_8bit',
        ),
    )

elif MODE == 'grpo':
    from trl import GRPOTrainer, GRPOConfig
    try:
        from unsloth import PatchFastRL
        PatchFastRL('GRPO', FastLanguageModel)
    except (ImportError, AttributeError, NameError):
        pass

    def _reward(completions, **kwargs):
        scores = []
        for text in completions:
            s = 0.0
            if len(text) > 400: s += 1.0
            elif len(text) > 150: s += 0.5
            else: s -= 0.5
            if text.count('\\n') > 3: s += 0.5
            scores.append(s)
        return scores

    def fmt_grpo(row):
        p = str(row.get('prompt') or row.get('instruction') or row.get('goal') or '')
        return {'prompt': _wrap(p)}

    ds_fmt  = ds.map(fmt_grpo, remove_columns=ds.column_names)
    ds_fmt  = ds_fmt.filter(lambda r: len(r['prompt']) > 20)
    trainer = GRPOTrainer(
        model=model, tokenizer=tokenizer, train_dataset=ds_fmt,
        reward_funcs=[_reward],
        args=GRPOConfig(
            max_prompt_length=384, max_completion_length=512, num_generations=4,
            per_device_train_batch_size=1, gradient_accumulation_steps=4,
            num_train_epochs=EPOCHS, learning_rate=5e-6,
            bf16=USE_BF16, fp16=USE_FP16, logging_steps=10,
            output_dir=OUTPUT_DIR, warmup_ratio=0.1,
            lr_scheduler_type='cosine', save_strategy='epoch',
            report_to='none', optim='adamw_8bit',
        ),
    )

print(f'Starting: {MODE.upper()}  agent={AGENT}  {len(ds_fmt)} examples...')
stats = trainer.train()
loss  = stats.metrics.get('train_loss', 0)
rt    = stats.metrics.get('train_runtime', 0)
print(f'\\nTraining complete!  Loss={loss:.4f}  Time={rt/60:.1f} min')'''

set_src(nb["cells"][training_idx], NEW_TRAINING_CELL)

nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"Saved patched notebook: {nb_path}")
print("Key fixes applied:")
print("  1. BF16/FP16 detection via torch.cuda.is_bf16_supported() (T4=FP16, A100=BF16)")
print("  2. max_length: 2048 -> 1024 (halved memory for sequences)")
print("  3. gradient_accumulation_steps: 8 -> 4")
print("  4. optim='adamw_8bit' (saves ~2GB on T4)")
