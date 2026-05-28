"""
v7 fix: no torch reinstall, detect compute cap in Cell 1, skip bitsandbytes on P100.
- P100 (sm_60): FP16 FP model, no bitsandbytes, batch=1 grad_acc=8
- T4+  (sm_75): 4-bit bitsandbytes NF4, batch=2 grad_acc=4
"""
import json, ast, re
from pathlib import Path

nb_path = Path('C:/Users/leer4/GH05T3/kaggle_train.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))

# ── Cell 1: hardware check — add COMPUTE_CAP ─────────────────────────────────
HW_SRC = [
    "# -- 0. Hardware check -------------------------------------------------------\n",
    "import subprocess, os\n",
    "result = subprocess.run(\n",
    "    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],\n",
    "    capture_output=True, text=True\n",
    ")\n",
    "if result.returncode == 0:\n",
    "    print('GPU:', result.stdout.strip())\n",
    "    BACKEND = 'cuda'\n",
    "    cap_r = subprocess.run(\n",
    "        ['nvidia-smi', '--query-gpu=compute_cap', '--format=csv,noheader'],\n",
    "        capture_output=True, text=True\n",
    "    )\n",
    "    COMPUTE_CAP = float(cap_r.stdout.strip().replace(',', '.')) if cap_r.returncode == 0 else 7.5\n",
    "    print(f'Compute capability: {COMPUTE_CAP}')\n",
    "else:\n",
    "    try:\n",
    "        import torch_xla.core.xla_model as xm\n",
    "        print('TPU:', xm.xla_device())\n",
    "        BACKEND = 'tpu'\n",
    "    except ImportError:\n",
    "        print('WARNING: No accelerator — CPU only')\n",
    "        BACKEND = 'cpu'\n",
    "    COMPUTE_CAP = 0\n",
    "print('Backend:', BACKEND)\n",
]

# ── Cell 4: install — no torch reinstall, skip bitsandbytes on P100 ──────────
INSTALL_SRC = [
    "# -- 3. Install deps ----------------------------------------------------------\n",
    "if BACKEND == 'cuda':\n",
    "    # Base training stack — use pre-installed torch (avoids torchvision conflicts)\n",
    "    os.system('pip install -q transformers peft accelerate trl datasets huggingface_hub')\n",
    "    if COMPUTE_CAP >= 7.5:\n",
    "        # T4 / A100 / V100-32: 4-bit bitsandbytes works (needs sm_7.5+)\n",
    "        os.system('pip install -q bitsandbytes')\n",
    "        LOAD_4BIT = True\n",
    "    else:\n",
    "        # P100 (sm_6.0): skip bitsandbytes — load FP16 instead, 3B model fits in 16 GB\n",
    "        LOAD_4BIT = False\n",
    "else:\n",
    "    os.system('pip install -q trl datasets transformers peft accelerate')\n",
    "    LOAD_4BIT = False\n",
    "print(f'Deps installed. 4-bit={LOAD_4BIT}')\n",
]

# ── Cell 7: model load — conditional 4-bit vs FP16 ───────────────────────────
MODEL_SRC = [
    "# -- 6a. Load model (4-bit on T4+, FP16 on P100) ----------------------------\n",
    "BASE_MODEL = 'Qwen/Qwen2.5-3B-Instruct'\n",
    "\n",
    "if BACKEND == 'cuda':\n",
    "    from transformers import AutoModelForCausalLM, AutoTokenizer\n",
    "    from peft import get_peft_model, LoraConfig, TaskType, prepare_model_for_kbit_training\n",
    "    import torch\n",
    "\n",
    "    HAS_BF16 = torch.cuda.is_bf16_supported()\n",
    "    TORCH_DTYPE = torch.bfloat16 if HAS_BF16 else torch.float16\n",
    "    print(f'sm={COMPUTE_CAP}  BF16={HAS_BF16}  4bit={LOAD_4BIT}  dtype={TORCH_DTYPE}')\n",
    "\n",
    "    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, token=HF_TOKEN)\n",
    "    if tokenizer.pad_token is None:\n",
    "        tokenizer.pad_token = tokenizer.eos_token\n",
    "    tokenizer.padding_side = 'right'\n",
    "\n",
    "    if LOAD_4BIT:\n",
    "        from transformers import BitsAndBytesConfig\n",
    "        bnb_config = BitsAndBytesConfig(\n",
    "            load_in_4bit=True,\n",
    "            bnb_4bit_compute_dtype=TORCH_DTYPE,\n",
    "            bnb_4bit_quant_type='nf4',\n",
    "            bnb_4bit_use_double_quant=True,\n",
    "        )\n",
    "        model = AutoModelForCausalLM.from_pretrained(\n",
    "            BASE_MODEL, quantization_config=bnb_config,\n",
    "            token=HF_TOKEN, device_map='auto',\n",
    "        )\n",
    "        model = prepare_model_for_kbit_training(model)\n",
    "    else:\n",
    "        # P100: pure FP16 — Qwen2.5-3B is ~6 GB, fits in 16 GB VRAM\n",
    "        model = AutoModelForCausalLM.from_pretrained(\n",
    "            BASE_MODEL, torch_dtype=TORCH_DTYPE,\n",
    "            token=HF_TOKEN, device_map='auto',\n",
    "        )\n",
    "\n",
    "    model.config.use_cache = False\n",
    "    lora_config = LoraConfig(\n",
    "        task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32, lora_dropout=0.05,\n",
    "        target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],\n",
    "        bias='none',\n",
    "    )\n",
    "    model = get_peft_model(model, lora_config)\n",
    "    model.print_trainable_parameters()\n",
]

# ── Cell 9: training — adjust batch for P100 ─────────────────────────────────
TRAIN_SRC = [
    "# -- 7. Format + train --------------------------------------------------------\n",
    "import torch\n",
    "from transformers import TrainingArguments\n",
    "\n",
    "def _wrap(goal):\n",
    "    return (\n",
    "        '<|im_start|>system\\n' + SYSTEM + '<|im_end|>\\n'\n",
    "        '<|im_start|>user\\n' + str(goal) + '<|im_end|>\\n'\n",
    "        '<|im_start|>assistant\\n'\n",
    "    )\n",
    "\n",
    "if BACKEND == 'cuda':\n",
    "    USE_BF16 = torch.cuda.is_bf16_supported()\n",
    "    USE_FP16 = not USE_BF16\n",
    "    BATCH    = 2 if LOAD_4BIT else 1   # FP16 uses more memory\n",
    "    GRAD_ACC = 4 if LOAD_4BIT else 8\n",
    "else:\n",
    "    USE_BF16 = False\n",
    "    USE_FP16 = False\n",
    "    BATCH    = 1\n",
    "    GRAD_ACC = 8\n",
    "\n",
    "print(f'BF16={USE_BF16}  FP16={USE_FP16}  batch={BATCH}  grad_acc={GRAD_ACC}')\n",
    "\n",
    "if MODE == 'sft':\n",
    "    from trl import SFTTrainer, SFTConfig\n",
    "\n",
    "    def fmt(row):\n",
    "        g = str(row.get('instruction') or row.get('goal') or row.get('prompt') or '')\n",
    "        r = str(row.get('response') or row.get('chosen') or '')\n",
    "        return {'text': _wrap(g) + r + '<|im_end|>'}\n",
    "\n",
    "    ds_fmt = ds.map(fmt, remove_columns=ds.column_names)\n",
    "    trainer = SFTTrainer(\n",
    "        model=model, tokenizer=tokenizer,\n",
    "        train_dataset=ds_fmt,\n",
    "        args=SFTConfig(\n",
    "            dataset_text_field='text',\n",
    "            max_seq_length=MAX_SEQ,\n",
    "            packing=False,\n",
    "            per_device_train_batch_size=BATCH,\n",
    "            gradient_accumulation_steps=GRAD_ACC,\n",
    "            num_train_epochs=EPOCHS, learning_rate=2e-4,\n",
    "            bf16=USE_BF16, fp16=USE_FP16, logging_steps=50,\n",
    "            output_dir=OUTPUT_DIR, warmup_ratio=0.1,\n",
    "            lr_scheduler_type='cosine', save_strategy='epoch', report_to='none',\n",
    "            gradient_checkpointing=True,\n",
    "            gradient_checkpointing_kwargs={'use_reentrant': False},\n",
    "            dataloader_pin_memory=False,\n",
    "        ),\n",
    "    )\n",
    "\n",
    "elif MODE == 'orpo':\n",
    "    from trl import ORPOTrainer, ORPOConfig\n",
    "\n",
    "    def fmt_orpo(row):\n",
    "        g = str(row.get('goal') or row.get('instruction') or '')\n",
    "        p = str(row.get('prompt') or ('GOAL: ' + g + '\\n\\nProvide a detailed sovereign response:'))\n",
    "        return {\n",
    "            'prompt':   _wrap(p),\n",
    "            'chosen':   str(row['chosen']) + '<|im_end|>',\n",
    "            'rejected': str(row['rejected']) + '<|im_end|>',\n",
    "        }\n",
    "\n",
    "    ds_fmt = ds.map(fmt_orpo, remove_columns=ds.column_names)\n",
    "    trainer = ORPOTrainer(\n",
    "        model=model, tokenizer=tokenizer, train_dataset=ds_fmt,\n",
    "        args=ORPOConfig(\n",
    "            max_length=MAX_SEQ, max_prompt_length=512, beta=0.1,\n",
    "            per_device_train_batch_size=1, gradient_accumulation_steps=8,\n",
    "            num_train_epochs=EPOCHS, learning_rate=8e-6,\n",
    "            bf16=USE_BF16, fp16=USE_FP16, logging_steps=50,\n",
    "            output_dir=OUTPUT_DIR, warmup_ratio=0.1,\n",
    "            lr_scheduler_type='cosine', save_strategy='epoch', report_to='none',\n",
    "        ),\n",
    "    )\n",
    "\n",
    "elif MODE == 'dpo':\n",
    "    from trl import DPOTrainer, DPOConfig\n",
    "\n",
    "    def fmt_dpo(row):\n",
    "        g = str(row.get('goal') or row.get('instruction') or '')\n",
    "        p = str(row.get('prompt') or ('GOAL: ' + g + '\\n\\nProvide a detailed sovereign response:'))\n",
    "        return {\n",
    "            'prompt':   _wrap(p),\n",
    "            'chosen':   str(row['chosen']) + '<|im_end|>',\n",
    "            'rejected': str(row['rejected']) + '<|im_end|>',\n",
    "        }\n",
    "\n",
    "    ds_fmt = ds.map(fmt_dpo, remove_columns=ds.column_names)\n",
    "    trainer = DPOTrainer(\n",
    "        model=model, ref_model=None, tokenizer=tokenizer, train_dataset=ds_fmt,\n",
    "        args=DPOConfig(\n",
    "            max_length=MAX_SEQ, max_prompt_length=512, beta=0.1,\n",
    "            per_device_train_batch_size=1, gradient_accumulation_steps=8,\n",
    "            num_train_epochs=EPOCHS, learning_rate=5e-6,\n",
    "            bf16=USE_BF16, fp16=USE_FP16, logging_steps=50,\n",
    "            output_dir=OUTPUT_DIR, warmup_ratio=0.1,\n",
    "            lr_scheduler_type='cosine', save_strategy='epoch', report_to='none',\n",
    "        ),\n",
    "    )\n",
    "\n",
    "elif MODE == 'grpo':\n",
    "    from trl import GRPOTrainer, GRPOConfig\n",
    "\n",
    "    def _reward(completions, **kwargs):\n",
    "        scores = []\n",
    "        for text in completions:\n",
    "            s = 0.0\n",
    "            if len(text) > 400: s += 1.0\n",
    "            elif len(text) > 150: s += 0.5\n",
    "            else: s -= 0.5\n",
    "            if text.count('\\n') > 3: s += 0.5\n",
    "            scores.append(s)\n",
    "        return scores\n",
    "\n",
    "    def fmt_grpo(row):\n",
    "        p = str(row.get('prompt') or row.get('instruction') or row.get('goal') or '')\n",
    "        return {'prompt': _wrap(p)}\n",
    "\n",
    "    ds_fmt = ds.map(fmt_grpo, remove_columns=ds.column_names)\n",
    "    ds_fmt = ds_fmt.filter(lambda r: len(r['prompt']) > 20)\n",
    "    trainer = GRPOTrainer(\n",
    "        model=model, tokenizer=tokenizer, train_dataset=ds_fmt,\n",
    "        reward_funcs=[_reward],\n",
    "        args=GRPOConfig(\n",
    "            max_prompt_length=512, max_completion_length=512, num_generations=4,\n",
    "            per_device_train_batch_size=1, gradient_accumulation_steps=8,\n",
    "            num_train_epochs=EPOCHS, learning_rate=5e-6,\n",
    "            bf16=USE_BF16, fp16=USE_FP16, logging_steps=50,\n",
    "            output_dir=OUTPUT_DIR, warmup_ratio=0.1,\n",
    "            lr_scheduler_type='cosine', save_strategy='epoch', report_to='none',\n",
    "        ),\n",
    "    )\n",
    "\n",
    "print(f'Starting: {MODE.upper()}  agent={AGENT}  {len(ds_fmt)} examples...')\n",
    "stats = trainer.train()\n",
    "loss  = stats.metrics.get('train_loss', 0)\n",
    "rt    = stats.metrics.get('train_runtime', 0)\n",
    "print(f'Training complete!  Loss={loss:.4f}  Time={rt/60:.1f} min')\n",
]

# Apply by cell content markers
PATCHES = [
    ('# ── 0. Hardware check', HW_SRC,      'Cell 1: hardware check'),
    ('pip install',            INSTALL_SRC,  'Cell 4: install'),
    ('BitsAndBytesConfig',     MODEL_SRC,    'Cell 7: model load'),
    ('SFTTrainer',             TRAIN_SRC,    'Cell 9: training'),
]

applied = set()
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    for marker, new_src, label in PATCHES:
        if marker in src and label not in applied:
            nb['cells'][i]['source'] = new_src
            print(f'  Patched cell {i}: {label}')
            applied.add(label)
            break

nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'Saved. Patches applied: {len(applied)}/4')

# Syntax check
print('\nSyntax check:')
all_ok = True
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    src_clean = re.sub(r'^%[^\n]+\n', '', src, flags=re.MULTILINE)
    try:
        ast.parse(src_clean)
        print(f'  [OK]  cell {i}')
    except SyntaxError as e:
        all_ok = False
        print(f'  [FAIL] cell {i} line {e.lineno}: {e.msg}')
        lines = src_clean.splitlines()
        for ln in lines[max(0,e.lineno-3):e.lineno+2]:
            print(f'         {ln}')
print('ALL OK' if all_ok else 'ERRORS FOUND')
