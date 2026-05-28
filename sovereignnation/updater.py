"""
SovereignNation Client Updater
==============================
Runs on each client machine. Checks for new agent versions daily,
downloads updated GGUFs, and hot-swaps them into Ollama.

How it works:
  - Polls a manifest URL (GitHub raw or simple HTTPS endpoint)
  - Compares local version against manifest
  - Downloads new GGUF if version changed
  - Runs `ollama create` to swap in the model
  - Logs everything to updates.log

Run on startup:  python updater.py --daemon
Run manually:    python updater.py --check
"""
import argparse, hashlib, json, logging, os, subprocess, sys, time
from pathlib import Path
import urllib.request

# ── Config ─────────────────────────────────────────────────────────────────────
MANIFEST_URL  = "https://raw.githubusercontent.com/leerobber/sovereign-releases/main/manifest.json"
INSTALL_DIR   = Path(os.environ.get("SOVEREIGN_DIR", r"C:\SovereignNation"))
LOG_FILE      = INSTALL_DIR / "updates.log"
CHECK_INTERVAL = 86400   # 24 hours
VERSION_FILE   = INSTALL_DIR / "installed_versions.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("updater")


def fetch_manifest() -> dict:
    with urllib.request.urlopen(MANIFEST_URL, timeout=15) as r:
        return json.loads(r.read().decode())


def load_installed() -> dict:
    if VERSION_FILE.exists():
        return json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    return {}


def save_installed(versions: dict):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(json.dumps(versions, indent=2), encoding="utf-8")


def verify_sha256(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest() == expected


def download_model(agent: str, url: str, sha256: str) -> Path:
    dest = INSTALL_DIR / f"{agent}.gguf"
    tmp  = INSTALL_DIR / f"{agent}.gguf.tmp"
    log.info(f"  Downloading {agent} from {url[:60]}...")
    urllib.request.urlretrieve(url, tmp)
    if sha256 and not verify_sha256(tmp, sha256):
        tmp.unlink()
        raise ValueError(f"SHA256 mismatch for {agent}")
    tmp.rename(dest)
    log.info(f"  Download complete: {dest.stat().st_size/1e9:.2f} GB")
    return dest


def install_model(agent: str, gguf_path: Path, system_prompt: str, version: str):
    mf = INSTALL_DIR / f"Modelfile.{agent}"
    mf.write_text(
        f"FROM {gguf_path.as_posix()}\n"
        f'SYSTEM """{system_prompt}"""\n'
        "PARAMETER temperature 0.7\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER num_ctx 4096\n",
        encoding="utf-8"
    )
    log.info(f"  Installing {agent}-sovereign v{version} into Ollama...")
    result = subprocess.run(
        ["ollama", "create", f"{agent}-sovereign", "-f", str(mf)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama create failed: {result.stderr[:200]}")
    log.info(f"  {agent}-sovereign v{version} is live.")


def check_and_update():
    log.info("Checking for SovereignNation updates...")
    try:
        manifest = fetch_manifest()
    except Exception as e:
        log.warning(f"Could not fetch manifest: {e}")
        return

    installed = load_installed()
    updated = []

    for agent, info in manifest.get("agents", {}).items():
        new_ver = info.get("version", "0")
        cur_ver = installed.get(agent, {}).get("version", "")
        if new_ver == cur_ver:
            log.info(f"  {agent}: v{new_ver} (current)")
            continue

        log.info(f"  {agent}: update available {cur_ver} -> {new_ver}")
        try:
            url = info.get("url", "")
            if not url:
                # No download URL in manifest — model is pre-installed locally.
                # Just record the version so we don't re-check on every boot.
                log.info(f"  {agent}: no download URL (pre-installed) — marking as v{new_ver}")
                installed[agent] = {"version": new_ver, "updated_at": time.time()}
                save_installed(installed)
                updated.append(f"{agent} v{new_ver} (pre-installed)")
                continue
            gguf = download_model(agent, url, info.get("sha256", ""))
            install_model(agent, gguf, info.get("system", ""), new_ver)
            installed[agent] = {"version": new_ver, "updated_at": time.time()}
            save_installed(installed)
            updated.append(f"{agent} v{new_ver}")
        except Exception as e:
            log.error(f"  Failed to update {agent}: {e}")

    if updated:
        log.info(f"Updates applied: {', '.join(updated)}")
    else:
        log.info("All agents up to date.")


def daemon_loop():
    log.info("SovereignNation Updater daemon started.")
    while True:
        check_and_update()
        log.info(f"Next check in {CHECK_INTERVAL//3600}h. Sleeping...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check",  action="store_true", help="Check once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously (daily checks)")
    args = parser.parse_args()

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    if args.check:
        check_and_update()
    elif args.daemon:
        daemon_loop()
    else:
        parser.print_help()
