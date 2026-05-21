# Mesh Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GH05T3 use one coherent peer-mesh contract across backend and dashboard, with live status, sync actions, and regression tests.

**Architecture:** Keep the v3 gateway as the source of truth for mesh state and expose a stable `/peers` API that can also surface GitHub relay and Tailscale discovery data. Update the dashboard peer panel and API helpers to consume that contract directly, then add regression tests for the route shapes and mesh sync helpers.

**Tech Stack:** FastAPI, Pydantic, React, Lucide, pytest, requests

---

### Task 1: Normalize mesh routes in the v3 gateway

**Files:**
- Modify: `backend/gateway_v3.py`

- [ ] **Step 1: Review the existing mesh endpoints and choose one public contract**

Use the current `/peers` family as the canonical API and keep the GitHub relay routes as nested mesh controls.

- [ ] **Step 2: Add compatibility aliases for the older `/peers/ping` and `/peers/sync/push` clients**

```python
@app.post("/peers/ping")
async def ping_peers_alias():
    return {"peers": await refresh_peers()["peers"]}


@app.post("/peers/sync/push")
async def push_sync_all_alias():
    return await github_mesh_sync()
```

- [ ] **Step 3: Make `/peers` return self info plus live peer discovery and GitHub relay metadata**

```python
@app.get("/peers")
async def get_peers():
    return {
        "self": {
            "label": os.environ.get("TAILSCALE_OWN_LABEL", "GH05T3"),
            "role": "primary",
            "url": f"http://{os.environ.get('TAILSCALE_OWN_IP', 'localhost')}:{GATEWAY_PORT}",
        },
        "peers": peer_registry.peers,
        "mesh": {
            "github_relay": {
                "push": "/github/mesh/push",
                "pull": "/github/mesh/pull",
                "sync": "/github/mesh/sync",
                "peers": "/github/mesh/peers",
            }
        },
    }
```

- [ ] **Step 4: Add a dedicated `/peers/refresh` handler that returns the refreshed peer list**

```python
@app.post("/peers/refresh")
async def refresh_peers():
    peers = await peer_registry.refresh()
    data = _mesh_contract()
    data["peers"] = peers
    data["count"] = len(peers)
    return data
```

- [ ] **Step 5: Run a syntax check on the gateway**

Run: `python -m py_compile backend/gateway_v3.py`
Expected: no output

### Task 2: Update the dashboard API helpers and peer panel

**Files:**
- Modify: `frontend/src/lib/ghostApi.js`
- Modify: `frontend/src/components/ghost/PeersPanel.jsx`

- [ ] **Step 1: Replace the old peer helper assumptions with the v3 gateway contract**

```javascript
export const gw3Peers = () => gw3.get("/peers").then((r) => r.data);
export const gw3PeersRefresh = () => gw3.post("/peers/refresh").then((r) => r.data);
export const gw3PeersPing = () => gw3.post("/peers/ping").then((r) => r.data);
export const gw3MeshSync = () => gw3.post("/github/mesh/sync").then((r) => r.data);
export const gw3MeshPeers = () => gw3.get("/github/mesh/peers").then((r) => r.data);
```

- [ ] **Step 2: Rework `PeersPanel` to show self status, live peers, and GitHub relay actions**

```jsx
import {
  gw3Peers, gw3PeersRefresh, gw3PeersRegister, gw3PeersRemove,
  gw3PeersPing, gw3PeersSync, gw3PeersRelayPeers,
} from "../../lib/ghostApi";
```

```jsx
const load = useCallback(async () => {
  const d = await gw3Peers();
  setData(d);
  setRelay(d?.mesh?.github_relay || null);
}, []);
```

- [ ] **Step 3: Add explicit refresh, ping, and sync controls for the canonical mesh**

```jsx
const handleRefresh = async () => {
  const d = await gw3PeersRefresh();
  setData((prev) => ({ ...(prev || {}), peers: d.peers, self: d.self }));
};
```

- [ ] **Step 4: Surface relay peers in the panel so operators can see GitHub-mediated sync state**

```jsx
const relayPeers = await gw3PeersRelayPeers();
```

- [ ] **Step 5: Run a frontend smoke build**

Run: `cd frontend && npm run build`
Expected: build completes without route or import errors

### Task 3: Add regression coverage for the unified mesh contract

**Files:**
- Add: `backend/tests/test_mesh_contract.py`

- [ ] **Step 1: Write a gateway contract test for `/peers` and `/peers/refresh`**

```python
def test_peers_contract(client):
    r = client.get("/peers")
    assert r.status_code == 200
    data = r.json()
    assert "self" in data
    assert "peers" in data
    assert "mesh" in data
```

- [ ] **Step 2: Write a compatibility test for `/peers/ping`**

```python
def test_peers_ping_alias(client):
    r = client.post("/peers/ping")
    assert r.status_code == 200
    assert "peers" in r.json()
```

- [ ] **Step 3: Write a compatibility test for GitHub mesh sync**

```python
def test_mesh_sync_alias(client, monkeypatch):
    r = client.post("/github/mesh/sync")
    assert r.status_code in (200, 503)
```

- [ ] **Step 4: Run the targeted backend test file**

Run: `pytest backend/tests/test_mesh_contract.py -q`
Expected: all tests pass
