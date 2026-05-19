"""
runpod_launcher.py — Sovereign RunPod Training Launcher

Usage:
  python runpod_launcher.py              # launch + train + auto-stop
  python runpod_launcher.py --status    # check running pod + tail log
  python runpod_launcher.py --stop      # stop running pod(s)
  python runpod_launcher.py --tail      # attach to live training log
  python runpod_launcher.py --cleanup   # stop ALL sovereign training pods
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY       = os.environ.get("RUNPOD_API_KEY", "")
HF_TOKEN      = os.environ.get("HF_TOKEN", "")
SSH_KEY_PUB   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIARR9yuDQlP7BJ8VKXq3o/bZlPLov71iDTRb2HBtfMQl claude-avery-training"
TRAIN_SCRIPT  = Path(__file__).parent / "train_sovereign_sft.py"
STATE_FILE    = Path(__file__).parent / "data" / "runpod_state.json"
LOG_FILE      = Path(__file__).parent / "data" / "train_run.log"
ERR_FILE      = Path(__file__).parent / "data" / "train_run_err.log"

# GPU preference order — cheapest first, then by price
GPU_PRIORITY  = [
    "NVIDIA RTX A5000",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 3090 Ti",
    "NVIDIA RTX A6000",
    "NVIDIA GeForce RTX 4090",
]
POD_IMAGE     = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
POD_NAME      = "avery-sovereign-training"

GQL_URL = ""  # set by _load_env


# ── Env loader ────────────────────────────────────────────────────────────────
def _load_env():
    global API_KEY, HF_TOKEN, GQL_URL
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip("'\"")
                os.environ.setdefault(k.strip(), v)
                if k.strip() == "RUNPOD_API_KEY" and not API_KEY:
                    API_KEY = v
                if k.strip() == "HF_TOKEN" and not HF_TOKEN:
                    HF_TOKEN = v
    GQL_URL = f"https://api.runpod.io/graphql?api_key={API_KEY}"


def _gql(query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = requests.post(GQL_URL, json=payload,
                      headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


# ── SSH key ───────────────────────────────────────────────────────────────────
def _ssh_key_path() -> str:
    candidates = [
        Path.home() / ".ssh" / "avery_training",
        Path.home() / ".ssh" / "runpod",
        Path.home() / ".ssh" / "id_ed25519",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    print(f"WARNING: No SSH private key found. Tried: {[str(c) for c in candidates]}")
    return str(Path.home() / ".ssh" / "avery_training")


# ── RunPod API ────────────────────────────────────────────────────────────────
def find_all_gpus_sorted() -> list:
    data = _gql("{ gpuTypes { id displayName memoryInGb communityPrice securePrice } }")
    eligible = [g for g in data["gpuTypes"]
                if (g.get("memoryInGb") or 0) >= 24
                and (g.get("communityPrice") or g.get("securePrice"))]
    priority_ids = {name: i for i, name in enumerate(GPU_PRIORITY)}
    def sort_key(g):
        pri   = priority_ids.get(g["displayName"], 99)
        price = g.get("communityPrice") or g.get("securePrice") or 99
        return (pri, price)
    eligible.sort(key=sort_key)
    return eligible


def start_pod(gpu_type_id: str, cloud_type: str = "COMMUNITY") -> dict:
    mutation = """
    mutation CreatePod($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id name desiredStatus
        runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } }
      }
    }
    """
    variables = {"input": {
        "cloudType":         cloud_type,
        "gpuCount":          1,
        "volumeInGb":        30,
        "containerDiskInGb": 30,
        "minVcpuCount":      4,
        "minMemoryInGb":     15,
        "gpuTypeId":         gpu_type_id,
        "name":              POD_NAME,
        "imageName":         POD_IMAGE,
        "ports":             "22/tcp",
        "volumeMountPath":   "/workspace",
        "env": [
            {"key": "PUBLIC_KEY",   "value": SSH_KEY_PUB},
            {"key": "HF_TOKEN",     "value": HF_TOKEN},
            {"key": "TRAIN_MODE",   "value": os.environ.get("TRAIN_MODE",  "orpo")},
            {"key": "TRAIN_SPLIT",  "value": os.environ.get("TRAIN_SPLIT", "bootstrap_dpo")},
            {"key": "TRAIN_AGENT",  "value": os.environ.get("TRAIN_AGENT", "avery")},
        ],
    }}
    data = _gql(mutation, variables)
    return data["podFindAndDeployOnDemand"]


def get_pod(pod_id: str) -> dict:
    query = """
    query GetPod($podId: String!) {
      pod(input: { podId: $podId }) {
        id name desiredStatus
        runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } }
      }
    }
    """
    return _gql(query, {"podId": pod_id})["pod"]


def list_all_pods() -> list:
    q = "{myself{pods{id name desiredStatus runtime{uptimeInSeconds ports{ip isIpPublic privatePort publicPort type}}}}}"
    return _gql(q)["myself"]["pods"]


def stop_pod(pod_id: str):
    mutation = """
    mutation StopPod($podId: String!) {
      podStop(input: { podId: $podId }) { id desiredStatus }
    }
    """
    return _gql(mutation, {"podId": pod_id})


def get_ssh_info(pod: dict):
    ports = (pod.get("runtime") or {}).get("ports") or []
    for p in ports:
        if p.get("privatePort") == 22 and p.get("isIpPublic"):
            return p["ip"], p["publicPort"]
    return None, None


# ── State ─────────────────────────────────────────────────────────────────────
def _save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ── SSH helpers ───────────────────────────────────────────────────────────────
def _scp_upload(ip: str, port: int, local: str, remote: str):
    key = _ssh_key_path()
    cmd = ["scp", "-i", key, "-P", str(port),
           "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
           local, f"root@{ip}:{remote}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"SCP failed: {result.stderr}")


def _ssh_run(ip: str, port: int, command: str, capture: bool = False, timeout: int = 30):
    key = _ssh_key_path()
    cmd = ["ssh", "-i", key, "-p", str(port),
           "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
           "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
           f"root@{ip}", command]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return subprocess.run(cmd, timeout=timeout)


def _check_training_done(ip: str, port: int) -> tuple[bool, dict | None]:
    """Return (done, info_dict). done=True means /workspace/training_complete.txt exists."""
    try:
        result = _ssh_run(ip, port,
                          "cat /workspace/training_complete.txt 2>/dev/null || echo NOT_DONE",
                          capture=True, timeout=20)
        out = result.stdout.strip() if result.returncode == 0 else "NOT_DONE"
        if "NOT_DONE" in out:
            return False, None
        try:
            return True, json.loads(out)
        except Exception:
            return True, {"raw": out}
    except subprocess.TimeoutExpired:
        return False, None
    except Exception as e:
        print(f"    [SSH check error: {e}]")
        return False, None


# ── Leak check: kill orphan pods before launching ─────────────────────────────
def _kill_orphan_pods():
    """Stop any sovereign training pods that are RUNNING without a local state."""
    pods = list_all_pods()
    running = [p for p in pods
               if p["name"] == POD_NAME and p["desiredStatus"] == "RUNNING"]
    if not running:
        return
    print(f"  [LEAK] {len(running)} orphan pod(s) found — stopping before launch:")
    for p in running:
        uptime = (p.get("runtime") or {}).get("uptimeInSeconds", "?")
        print(f"    Pod {p['id']} (uptime {uptime}s) -> stopping")
        try:
            stop_pod(p["id"])
        except Exception as e:
            print(f"    [stop error: {e}]")
    print("  [LEAK] Orphans cleared. Sleeping 10s...")
    time.sleep(10)


# ── Main: launch ──────────────────────────────────────────────────────────────
def launch(train_mode: str = None, train_split: str = None):
    _load_env()
    if not API_KEY:
        print("ERROR: RUNPOD_API_KEY not set in .env"); sys.exit(1)
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN not set in .env"); sys.exit(1)

    train_mode  = train_mode  or os.environ.get("TRAIN_MODE",  "orpo")
    train_split = train_split or os.environ.get("TRAIN_SPLIT", "bootstrap_dpo")

    print("\n+==========================================+")
    print("|  SOVEREIGN RUNPOD TRAINING LAUNCHER      |")
    print("+==========================================+\n")
    print(f"  Mode  : {train_mode.upper()}")
    print(f"  Split : {train_split}")
    print(f"  SSH   : {_ssh_key_path()}")
    print()

    # ── Kill any orphan pods ──────────────────────────────────────────────────
    print("[0/6] Checking for orphan pods...")
    _kill_orphan_pods()
    print("  Clean.")

    # ── Find GPU ──────────────────────────────────────────────────────────────
    print("\n[1/6] Finding available GPU...")
    gpus = find_all_gpus_sorted()
    pod = None
    for cloud_type in ["COMMUNITY", "SECURE"]:
        if pod:
            break
        if cloud_type == "SECURE":
            print("  Community cloud dry — trying Secure cloud...")
        for g in gpus:
            price = (g.get("communityPrice") if cloud_type == "COMMUNITY"
                     else g.get("securePrice")) or 99
            print(f"  [{cloud_type}] {g['displayName']} ({g['memoryInGb']}GB) @ ${price:.3f}/hr...")
            try:
                # Inject mode into env before start
                os.environ["TRAIN_MODE"]  = train_mode
                os.environ["TRAIN_SPLIT"] = train_split
                pod = start_pod(g["id"], cloud_type=cloud_type)
                print(f"  SUCCESS: {g['displayName']} @ ${price:.3f}/hr")
                break
            except Exception as e:
                msg = str(e)
                if any(x in msg for x in ["SUPPLY_CONSTRAINT", "no longer any instances",
                                           "does not have the resources", "RUNPOD",
                                           "resources are unavailable"]):
                    print("  Unavailable — trying next...")
                    continue
                raise

    if pod is None:
        print("ERROR: No GPUs available. Try again in a few minutes.")
        sys.exit(1)

    pod_id = pod["id"]
    print(f"\n[2/6] Pod started: {pod_id}  Status: {pod['desiredStatus']}")
    _save_state({"pod_id": pod_id, "started_at": time.time(),
                 "train_mode": train_mode, "train_split": train_split})

    # ── Wait for SSH ──────────────────────────────────────────────────────────
    print("[3/6] Waiting for SSH...")
    ip, port = None, None
    for attempt in range(60):
        time.sleep(15)
        try:
            pod = get_pod(pod_id)
            ip, port = get_ssh_info(pod)
            status = pod.get("desiredStatus", "?")
            print(f"  [{attempt+1}/60] Status: {status}  SSH: {ip}:{port}")
            if ip and port:
                break
        except Exception as e:
            print(f"  [{attempt+1}/60] API error: {e}")
    else:
        print("  ERROR: Pod never got SSH. Run: python runpod_launcher.py --cleanup")
        sys.exit(1)

    print("  Waiting 25s for sshd to initialize...")
    time.sleep(25)

    # ── Upload ────────────────────────────────────────────────────────────────
    print(f"\n[4/6] Uploading training script to {ip}:{port}...")
    _scp_upload(ip, port, str(TRAIN_SCRIPT), "/workspace/train_sovereign_sft.py")
    print("  Uploaded.")
    _save_state({"pod_id": pod_id, "ip": ip, "port": port,
                 "started_at": time.time(), "train_mode": train_mode,
                 "train_split": train_split,
                 "train_agent": os.environ.get("TRAIN_AGENT", "avery")})

    # ── Launch ────────────────────────────────────────────────────────────────
    print(f"\n[5/6] Launching training on pod...")
    train_agent = os.environ.get("TRAIN_AGENT", "avery")
    train_cmd = (
        f"export HF_TOKEN={HF_TOKEN}; "
        f"export TRAIN_MODE={train_mode}; "
        f"export TRAIN_SPLIT={train_split}; "
        f"export TRAIN_AGENT={train_agent}; "
        f"nohup python /workspace/train_sovereign_sft.py "
        f"--mode {train_mode} --agent {train_agent} "
        + (f"--split {train_split} " if train_split else "")
        + f"> /workspace/train.log 2>&1 & echo LAUNCHED"
    )
    _ssh_run(ip, port, train_cmd, timeout=90)

    print(f"""
  Training is running on the pod (nohup — survives terminal close).

  To watch live:
    ssh -i {_ssh_key_path()} -p {port} root@{ip} "tail -f /workspace/train.log"
  Or:
    python runpod_launcher.py --tail

  To check status:
    python runpod_launcher.py --status
""")

    # ── Monitor ───────────────────────────────────────────────────────────────
    print("[6/6] Monitoring for completion (Ctrl+C safe — pod keeps running)...")
    _monitor(pod_id, ip, port)


def _monitor(pod_id: str, ip: str, port: int, max_minutes: int = 180):
    """Poll for training_complete.txt. Safe to kill — pod keeps running."""
    log_lines = []
    for minute in range(1, max_minutes + 1):
        time.sleep(60)

        # Re-fetch SSH info in case of pod restart
        try:
            pod = get_pod(pod_id)
            new_ip, new_port = get_ssh_info(pod)
            if new_ip:
                ip, port = new_ip, new_port
        except Exception:
            pass

        done, info = _check_training_done(ip, port)

        # Also tail log every 5 min
        if minute % 5 == 0:
            try:
                result = _ssh_run(ip, port, "tail -3 /workspace/train.log", capture=True, timeout=15)
                snippet = result.stdout.strip().replace("\n", " | ")
                print(f"  [{minute}m] {snippet[:120]}")
            except Exception:
                print(f"  [{minute}m] (log unavailable)")
        else:
            print(f"  [{minute}m] {'DONE' if done else 'training...'}")

        if done:
            _handle_completion(pod_id, info)
            return

    # Timeout reached
    print(f"\n  TIMEOUT: {max_minutes} minutes reached.")
    print("  Training may still be running. Check with: python runpod_launcher.py --status")
    print(f"  SSH: ssh -i {_ssh_key_path()} -p {port} root@{ip} 'tail -50 /workspace/train.log'")
    # Save current state so --status can reconnect
    state = _load_state()
    state.update({"ip": ip, "port": port, "pod_id": pod_id})
    _save_state(state)


def _handle_completion(pod_id: str, info: dict):
    print("\n  *** TRAINING COMPLETE ***")
    if info:
        print(f"  Model  : {info.get('model', '?')}")
        loss = info.get('loss')
        rt   = info.get('runtime_s', 0)
        print(f"  Loss   : {loss:.4f}" if loss else "  Loss   : ?")
        print(f"  Time   : {rt/60:.1f} min" if rt else "  Time   : ?")

    print("\n  Stopping pod to save credits...")
    try:
        stop_pod(pod_id)
        print(f"  Pod {pod_id} stopped.")
    except Exception as e:
        print(f"  Stop error: {e}")
    _save_state({})

    print("\n  Next step: python merge_and_convert.py")
    print("  LoRA: https://huggingface.co/tastytator/avery-sovereign-lora\n")


# ── CLI: --status ─────────────────────────────────────────────────────────────
def status():
    _load_env()
    state = _load_state()

    # Try state-based lookup first
    pod_id = state.get("pod_id")
    if not pod_id:
        print("No pod in local state. Checking RunPod for running pods...")
        pods = [p for p in list_all_pods()
                if p["name"] == POD_NAME and p["desiredStatus"] == "RUNNING"]
        if not pods:
            print("  No running sovereign pods found.")
            return
        print(f"  Found {len(pods)} running pod(s):")
        for p in pods:
            ip, port = get_ssh_info(p)
            uptime   = (p.get("runtime") or {}).get("uptimeInSeconds", "?")
            print(f"  Pod {p['id']}  uptime={uptime}s  SSH={ip}:{port}")
            if ip and port:
                result = _ssh_run(ip, port, "tail -20 /workspace/train.log", capture=True, timeout=20)
                print("\n--- Last 20 lines of train.log ---")
                print(result.stdout or "(empty)")
        return

    print(f"  Pod    : {pod_id}")
    print(f"  Mode   : {state.get('train_mode', '?')}")
    print(f"  Split  : {state.get('train_split', '?')}")
    try:
        pod  = get_pod(pod_id)
        ip, port = get_ssh_info(pod)
        print(f"  Status : {pod.get('desiredStatus')}")
        print(f"  SSH    : {ip}:{port}")
        if ip and port:
            done, info = _check_training_done(ip, port)
            print(f"  Done   : {done}")
            if done:
                print(f"  Info   : {info}")
                print("\n  Run: python runpod_launcher.py --stop")
            else:
                result = _ssh_run(ip, port, "tail -20 /workspace/train.log", capture=True, timeout=20)
                print("\n--- Last 20 lines of train.log ---")
                print(result.stdout or "(empty)")
    except Exception as e:
        print(f"  API error: {e}")


# ── CLI: --tail ───────────────────────────────────────────────────────────────
def tail():
    _load_env()
    state = _load_state()
    ip, port = state.get("ip"), state.get("port")
    pod_id   = state.get("pod_id")

    if not ip and pod_id:
        pod = get_pod(pod_id)
        ip, port = get_ssh_info(pod)
    if not ip:
        pods = [p for p in list_all_pods()
                if p["name"] == POD_NAME and p["desiredStatus"] == "RUNNING"]
        if pods:
            ip, port = get_ssh_info(pods[0])
    if not ip:
        print("No running pod found."); return

    key = _ssh_key_path()
    print(f"Tailing train.log on {ip}:{port}  (Ctrl+C to detach)\n")
    subprocess.run(["ssh", "-i", key, "-p", str(port),
                    "-o", "StrictHostKeyChecking=no",
                    f"root@{ip}", "tail -f /workspace/train.log"])


# ── CLI: --stop ───────────────────────────────────────────────────────────────
def stop():
    _load_env()
    state  = _load_state()
    pod_id = state.get("pod_id")
    if pod_id:
        try:
            stop_pod(pod_id)
            print(f"Stopped pod {pod_id}")
        except Exception as e:
            print(f"Error stopping {pod_id}: {e}")
        _save_state({})
    else:
        print("No pod in local state.")


# ── CLI: --cleanup ────────────────────────────────────────────────────────────
def cleanup():
    _load_env()
    pods = list_all_pods()
    running = [p for p in pods
               if p["name"] == POD_NAME and p["desiredStatus"] == "RUNNING"]
    if not running:
        print("No running sovereign pods."); return
    print(f"Stopping {len(running)} running pod(s):")
    for p in running:
        try:
            stop_pod(p["id"])
            print(f"  Stopped {p['id']}")
        except Exception as e:
            print(f"  Error {p['id']}: {e}")
    _save_state({})
    print("Done.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Sovereign RunPod Launcher")
    p.add_argument("--status",  action="store_true", help="Check running pod status + log")
    p.add_argument("--stop",    action="store_true", help="Stop the tracked pod")
    p.add_argument("--tail",    action="store_true", help="Attach to live training log")
    p.add_argument("--cleanup", action="store_true", help="Stop ALL sovereign pods")
    p.add_argument("--mode",    default="",  help="Training mode: sft / orpo / dpo")
    p.add_argument("--split",   default="",  help="HF split to train on")
    args = p.parse_args()

    if args.status:
        status()
    elif args.stop:
        stop()
    elif args.tail:
        tail()
    elif args.cleanup:
        cleanup()
    else:
        launch(train_mode=args.mode or None, train_split=args.split or None)
