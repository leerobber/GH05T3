from pathlib import Path
env_path = Path(r'C:\Users\leer4\GH05T3\.env')
hf_token = ''
for line in env_path.read_text(encoding='utf-8').splitlines():
    if line.startswith('HF_TOKEN='):
        hf_token = line.split('=', 1)[1].strip().strip("'\"")

import requests
from huggingface_hub import HfApi
api = HfApi(token=hf_token)

repos = {
    'avery':    'tastytator/avery-sovereign-lora',
    'forge':    'tastytator/forge-sovereign-lora',
    'oracle':   'tastytator/oracle-sovereign-lora',
    'codex':    'tastytator/codex-sovereign-lora',
    'sentinel': 'tastytator/sentinel-sovereign-lora',
    'nexus':    'tastytator/nexus-sovereign-lora',
}

for name, repo in repos.items():
    try:
        info = api.repo_info(repo, repo_type='model')
        url = f'https://huggingface.co/{repo}/resolve/main/adapter_config.json'
        r = requests.get(url, headers={'Authorization': f'Bearer {hf_token}'}, timeout=5)
        cfg = r.json()
        base = cfg.get('base_model_name_or_path', '?').split('/')[-1]
        r_val = cfg.get('r', '?')
        alpha = cfg.get('lora_alpha', '?')
        updated = str(info.lastModified)[:16]
        print(f"{name}: base={base}  r={r_val}  alpha={alpha}  updated={updated}")
    except Exception as e:
        print(f"{name}: ERROR {e}")
