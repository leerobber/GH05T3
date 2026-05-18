"""
check_pod.py — Quick RunPod status tool.

Usage:
  python check_pod.py            # list all pods + SSH info
  python check_pod.py --stop     # stop all RUNNING sovereign pods
  python check_pod.py --tail     # attach to live training log
"""
import argparse, json, os, subprocess
from pathlib import Path

def _load_env():
    env = {}
    for line in (Path(__file__).parent / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    return env

_load_env()

import requests

API_KEY = os.environ.get("RUNPOD_API_KEY", "")
GQL_URL = f"https://api.runpod.io/graphql?api_key={API_KEY}"
SSH_KEY = str(Path.home() / ".ssh" / "avery_training")


def _gql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = requests.post(GQL_URL, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def list_pods():
    q = "{myself{pods{id name desiredStatus runtime{uptimeInSeconds ports{ip isIpPublic privatePort publicPort type}}}}}"
    return _gql(q)["myself"]["pods"]


def get_ssh(pod):
    ports = (pod.get("runtime") or {}).get("ports") or []
    for p in ports:
        if p.get("privatePort") == 22 and p.get("isIpPublic"):
            return p["ip"], p["publicPort"]
    return None, None


def stop_pod(pod_id):
    m = """mutation StopPod($podId: String!) {
      podStop(input: { podId: $podId }) { id desiredStatus }
    }"""
    return _gql(m, {"podId": pod_id})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--tail", action="store_true")
    args = ap.parse_args()

    pods = list_pods()
    print(f"\nAll pods ({len(pods)} total):\n")
    for p in pods:
        ip, port = get_ssh(p)
        uptime   = (p.get("runtime") or {}).get("uptimeInSeconds", "-")
        ssh_str  = f"{ip}:{port}" if ip else "no-ssh"
        print(f"  {p['id']}  {p['name']:<30}  {p['desiredStatus']:<10}  uptime={uptime}s  {ssh_str}")

    running = [p for p in pods if p["desiredStatus"] == "RUNNING"]
    print(f"\nRunning: {len(running)}")

    if args.stop:
        for p in running:
            try:
                stop_pod(p["id"])
                print(f"  Stopped {p['id']}")
            except Exception as e:
                print(f"  Error stopping {p['id']}: {e}")
        return

    if args.tail:
        sovereign = [p for p in running if "avery" in p["name"].lower() or "sovereign" in p["name"].lower()]
        if not sovereign:
            print("No sovereign training pods running."); return
        p    = sovereign[0]
        ip, port = get_ssh(p)
        if not ip:
            print(f"Pod {p['id']} has no SSH yet."); return
        print(f"\nTailing train.log on {ip}:{port}  (Ctrl+C to detach)\n")
        subprocess.run(["ssh", "-i", SSH_KEY, "-p", str(port),
                        "-o", "StrictHostKeyChecking=no",
                        f"root@{ip}", "tail -f /workspace/train.log"])
        return

    if running:
        print(f"\nTo attach to training log:  python check_pod.py --tail")
        print(f"To stop all running:        python check_pod.py --stop")
        print(f"\nDirect SSH:")
        for p in running:
            ip, port = get_ssh(p)
            if ip:
                print(f"  ssh -i {SSH_KEY} -p {port} root@{ip} 'tail -f /workspace/train.log'")


if __name__ == "__main__":
    main()
