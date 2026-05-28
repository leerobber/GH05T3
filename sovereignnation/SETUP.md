# SovereignNation — Setup Guide

## What This Is

A local AI platform with 7 specialist modules that runs entirely on your machine.
No cloud, no API keys, no internet required after setup.
The demo focuses on accounting/tax research but the agents work for any professional domain.

---

## Prerequisites (install these first)

### 1. Python 3.11+
Download from: https://www.python.org/downloads/
- During install: check "Add Python to PATH"

### 2. Ollama (local AI model server)
Download from: https://ollama.com/download
- Install and run it — it runs in the background automatically

### 3. Pull a model
Open a terminal (Command Prompt or PowerShell) and run:

```
ollama pull llama3.2:3b
```

This downloads a ~2GB model. Good balance of speed and quality.
For better quality (needs 8GB+ RAM): `ollama pull mistral`

---

## Running the Demo

### Step 1 — Start the server
Open a terminal in this folder and run:

```
python serve.py
```

You should see:
```
  SovereignNation Client UI  v2.0
  Local  : http://localhost:7861
  Ollama : ONLINE
```

### Step 2 — Open the demo UI
Open Chrome and go to: http://localhost:7861

### Step 3 — Use it
Click any agent in the left sidebar, type a question, hit Submit.
Or click a demo card on the welcome screen to see a pre-built scenario run.

---

## Important: Model Names

The demo is configured to use custom model names (gh05t3, avery-sovereign, etc.)
that were trained specifically for this build. On your machine, you need to either:

**Option A (easiest):** Edit client/index.html
- Open client/index.html in a text editor (Notepad++, VS Code)
- Find every instance of `data-agent="avery-sovereign"` etc. and change to your model name
- Change `data-agent="gh05t3:latest"` to `data-agent="llama3.2:3b"` (or whatever you pulled)
- Do the same in the SYSTEM_PROMPTS and DEMO_PROMPTS sections

**Option B:** Pull models with the exact names
```
ollama pull mistral
ollama cp mistral avery-sovereign
ollama cp mistral forge-sovereign
ollama cp mistral oracle-sovereign
ollama cp mistral codex-sovereign
ollama cp mistral sentinel-sovereign
ollama cp mistral nexus-sovereign
ollama cp mistral gh05t3:latest
```
This makes copies of mistral under each expected name. All 7 agents work immediately.

Option B is recommended — takes 2 minutes and requires no code editing.

---

## Recording Mode (for Loom demo recording)

Open: http://localhost:7861/?autoplay=1

- Left panel: teleprompter script (press Space to advance lines)
- Right panel: demo fires automatically after 6 seconds
- No clicking required — just read the script out loud

---

## Files in This Package

| File | Purpose |
|------|---------|
| serve.py | The server — proxies Ollama API, serves the UI |
| client/index.html | The demo chat UI |
| landing/index.html | Marketing landing page |
| DEMO_ON.bat | Activates demo mode (Windows only) |
| DEMO_OFF.bat | Deactivates demo mode (Windows only) |
| START_QUICKTUNNEL.bat | Creates a public tunnel URL for remote access |

---

## Quick Troubleshooting

**"Inference service offline" in the UI**
→ Ollama isn't running. Open Ollama from your Start menu or run `ollama serve`

**Agent shows "loading" and never responds**
→ The model name in the UI doesn't match what you have installed
→ Run `ollama list` to see installed models, then follow Option A or B above

**Port 7861 already in use**
→ Change `PORT = 7861` in serve.py to any unused port (e.g. 7862)

---

## Questions?

Email: leer4030@gmail.com
