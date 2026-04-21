# GH05T3 — Native Windows

Run GH05T3 locally on your LOQ. No Docker, no subscriptions, no cloud.

## Install (one-time, ~5 min)

1. Open **PowerShell as Administrator** (right-click → "Run as Administrator").
2. Navigate to this folder:

   ```powershell
   cd path\to\gh05t3\native\windows
   ```

3. Allow the script to run, then install:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\install.ps1
   ```

   This installs (via winget):
   - Python 3.11
   - Node.js 20 + Yarn
   - MongoDB Community Edition
   - All backend + frontend dependencies (pip + yarn)
   - Voice stack: `faster-whisper`, `openwakeword`, `edge-tts`, `sounddevice`
   - Builds the frontend into a static bundle

   Creates `%USERPROFILE%\gh05t3\` with everything inside.
   Adds a **Startup shortcut** so GH05T3 boots with Windows.

4. Edit `%USERPROFILE%\gh05t3\backend\.env` if you want to set:
   - `EMERGENT_LLM_KEY` — for Claude Sonnet chat quality (optional)
   - Or leave empty and use Google AI Studio / Groq free keys from the UI.

## Run

```powershell
cd %USERPROFILE%\gh05t3
.\run.bat
```

Or just log out and back in — she auto-starts.

What happens:
- MongoDB starts on 127.0.0.1:27017 (data in `.\mongo-data\`)
- Backend on http://localhost:8001 (FastAPI + all Phase 1–5 features)
- Frontend on http://localhost:3210 (prebuilt static bundle)
- **Tray icon** appears in the notification area. Right-click for menu.
- Dashboard auto-opens in your browser.

## Tray menu

| Item | Action |
|---|---|
| Open Dashboard | Opens http://localhost:3210 |
| Hey GH05T3 (voice) | Starts / stops the wake-word + voice loop |
| GhostEye | Toggles ambient screen observation (requires paired companion) |
| Pause Ghost | Pauses the APScheduler (stops nightly jobs) |
| Quit GH05T3 | Graceful shutdown of backend, frontend, MongoDB |

## Voice: "Hey Jarvis" → speak → she replies

`openwakeword` ships with pre-trained models for **"hey jarvis" / "alexa" / "hey mycroft"**.
A custom "hey GH05T3" model needs ~30 sec of your voice to train — separate one-time step.

Say the wake word → she says "yes?" → talk → she transcribes with Whisper (on your
RTX 5050 via CUDA if available) → replies via gateway → speaks via Edge TTS neural voice.

### Push-to-talk fallback
If wake-word fails (mic permission, no model), it drops into **Hold F8 to talk** mode.

## Expose to your phone over Tailscale

1. Install [Tailscale](https://tailscale.com/) on your LOQ and your Android phone (both free).
2. Get your laptop's Tailscale hostname, e.g. `loq15.tail-scale.ts.net`.
3. On your phone, open `http://loq15.tail-scale.ts.net:3210` — bookmark / Add to Home Screen.
4. Voice input works via Chrome SpeechRecognition. Full dashboard works.

## Cost breakdown

| | Price |
|---|---|
| MongoDB Community | Free |
| Python + FastAPI | Free |
| Node + React | Free |
| Wake-word (openwakeword) | Free, offline |
| Speech-to-text (faster-whisper) | Free, offline (GPU-accelerated on your RTX) |
| Text-to-speech (Edge TTS) | Free, online (uses Azure demo endpoint) |
| Tailscale | Free personal plan |
| Google AI / Groq nightly LLM | Free tier generous |
| **Total** | **$0 / month** |

Optional: when you stand up Ollama locally (any day), add `OLLAMA_GATEWAY_URL`
to `.env` and *even* the nightly LLM goes fully offline.

## Update later

When you pull a new version of the source, re-run `install.ps1` to refresh files +
rebuild the frontend. Your data (Mongo, memories, goals, journal) is preserved.

## Uninstall

- Delete `%USERPROFILE%\gh05t3\`
- Remove `GH05T3.lnk` from `shell:startup`
- Optionally `winget uninstall MongoDB.Server` if nothing else uses it.

## Troubleshooting

**Mongo won't start** → port 27017 taken by another Mongo? Change `MONGO_URL` in `.env`
and `--port` in `run.bat`.

**Dashboard 404 on refresh** → the http.server doesn't know about React routes;
use `http://localhost:3210/` as root. All routes are under `/#` or `/`.

**Wake-word doesn't trigger** → mic permission, try push-to-talk (F8). Check
`openwakeword` downloaded its ONNX models on first run (~50MB, one-time).

**No edge-tts sound** → speaker permissions, or fallback to `pyttsx3` (SAPI) by
editing `voice.py` to use `pyttsx3.init().say(text)`.
