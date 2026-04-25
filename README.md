# 👻 GH05T3

Offline AI client with Memory Palace and HCM vector state. Runs fully local via Qwen2.5-1.5B.

## Quick Start

```bash
git clone https://github.com/leerobber/GH05T3.git
cd GH05T3
pip install -r requirements.txt
python ghost_bootstrap.py   # first run — installs + downloads model
python ghost_client.py      # subsequent runs
```

## Requirements

- Python 3.10+
- ~1.5GB disk for model cache (downloaded once)
- CPU inference — no GPU required

## Commands

| Command | Description |
|---------|-------------|
| `status` | Show mode, model, memory count |
| `goals` | List active Autotelic Engine goals |
| `recall <term>` | Search Memory Palace |
| `help` | Show command list |
| `exit` | Quit |

## Architecture

- **Memory Palace**: 83 memories across Identity, Skills, Projects, People, Knowledge, Decisions
- **HCM Vectors**: 146 hybrid cognitive map vectors (target: 200)
- **Model**: Qwen2.5-1.5B-Instruct (CPU, offline)
- **Autotelic Engine**: 21 active self-directed goals
