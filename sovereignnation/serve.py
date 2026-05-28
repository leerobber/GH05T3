"""
SovereignNation Client Server  v2.0
=====================================
Serves the client UI AND proxies all Ollama API calls server-side.
This is critical: the client JS uses relative URLs (/api/*) so the
cloudflared tunnel works for remote demo clients — they never need
Ollama on their own machine.

Endpoints:
  GET  /health       → JSON status (ollama up/down, models loaded)
  GET  /api/*        → proxied to http://localhost:11434/api/*
  POST /api/*        → proxied, with streaming NDJSON passthrough
  GET  /*            → static files from ./client/

Run: python serve.py
"""

import http.server
import json
import logging
import os
import socketserver
import sys
import urllib.error
import urllib.request
from pathlib import Path

CLIENT_DIR   = Path(__file__).parent / "client"
PORT         = 7861
OLLAMA       = "http://localhost:11434"
PAYMENTS     = "http://localhost:7862"
VERSION      = "2.0.0"
TUNNEL_URLS  = Path(__file__).parent.parent / "data" / "tunnel_urls.json"
DEMO_FLAG    = Path(__file__).parent.parent / "data" / "demo_mode.flag"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("sovereign-serve")


class SovereignHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CLIENT_DIR), **kwargs)

    # ── CORS headers on every response ──────────────────────────────────────
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    # ── GET ──────────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            self._health()
            return
        if self.path in ("/tunnel-urls", "/tunnel-urls.json"):
            self._tunnel_urls()
            return
        # ── Payments proxy ───────────────────────────────────────────────────
        if self.path.startswith(("/checkout", "/portal")):
            # These return 303 redirects — forward the redirect to the browser
            self._proxy_redirect(PAYMENTS + self.path)
            return
        if self.path.startswith(("/prices", "/payments-log", "/customers", "/verify-key")):
            self._proxy_get(PAYMENTS + self.path)
            return
        if self.path.startswith("/success"):
            # Serve success.html from client dir, preserving query params
            self._serve_page("success.html")
            return
        if self.path.startswith("/cancel"):
            self._serve_page("cancel.html")
            return
        if self.path.startswith("/api/"):
            # ── Access control check ─────────────────────────────────────────
            denied = self._access_denied()
            if denied:
                return
            self._proxy_get(OLLAMA + self.path)
            return
        super().do_GET()

    # ── POST ─────────────────────────────────────────────────────────────────
    def do_POST(self):
        if self.path.startswith("/api/"):
            # ── Access control check ─────────────────────────────────────────
            denied = self._access_denied()
            if denied:
                return
            self._proxy_post(OLLAMA + self.path)
            return
        if self.path.startswith("/webhook"):
            self._proxy_post_raw(PAYMENTS + self.path)
            return
        self._json_response(404, {"error": "not found"})

    # ── Access control ────────────────────────────────────────────────────────
    def _access_denied(self) -> bool:
        """
        Check the request's SN-Key header (or ?key= param) against the payments
        service.  Returns True and writes error response if access should be blocked.
        Returns False if access is allowed (or payments service is unreachable —
        fail-open so demos still work when payments is down).

        Demo mode bypass: if data/demo_mode.flag exists, all API access is
        allowed unconditionally so live prospect demos work without a key.
        """
        # Demo mode — bypass auth entirely so prospects can use the live demo
        if DEMO_FLAG.exists():
            return False

        # Extract key from header or query param
        key = self.headers.get("X-SN-Key") or self.headers.get("x-sn-key")
        if not key:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            key = (qs.get("key") or qs.get("sn_key") or [None])[0]

        if not key:
            self._json_response(401, {
                "error": "Access key required",
                "message": (
                    "Include your SovereignNation API key as the X-SN-Key header "
                    "or ?key= parameter. Check your welcome email for your key."
                ),
            })
            return True

        # Verify against payments service
        try:
            import urllib.parse
            verify_url = f"{PAYMENTS}/verify-key?key={urllib.parse.quote(key)}"
            req = urllib.request.Request(verify_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return False   # valid + active — allow through
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            try:
                detail = __import__("json").loads(body).get("detail", body)
            except Exception:
                detail = body
            self._json_response(e.code, {"error": detail})
            return True
        except Exception:
            # Payments service unreachable — fail open (don't block real clients)
            log.warning("Access check skipped — payments service unreachable")
            return False

        return False

    # ── /tunnel-urls ─────────────────────────────────────────────────────────
    def _tunnel_urls(self):
        try:
            data = json.loads(TUNNEL_URLS.read_text(encoding="utf-8"))
        except Exception:
            data = {"chat": None, "landing": None, "error": "tunnel_urls.json not found"}
        self._json_response(200, data)

    # ── /health ───────────────────────────────────────────────────────────────
    def _health(self):
        ollama_ok = False
        models    = []
        try:
            resp = urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3)
            data = json.loads(resp.read().decode())
            models    = [m["name"] for m in data.get("models", [])]
            ollama_ok = True
        except Exception:
            pass
        self._json_response(200, {
            "status":  "ok",
            "server":  f"SovereignNation v{VERSION}",
            "ollama":  ollama_ok,
            "models":  models,
            "count":   len(models),
        })

    # ── Proxy GET (e.g. /api/tags) ────────────────────────────────────────────
    def _proxy_get(self, url):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type",   "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.URLError:
            self._json_response(502, {"error": "Ollama is offline — run: ollama serve"})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── Proxy POST with streaming passthrough (e.g. /api/chat) ───────────────
    def _proxy_post(self, url):
        length  = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)

        try:
            streaming = json.loads(payload).get("stream", False)
        except Exception:
            streaming = False

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                ct = resp.headers.get("Content-Type", "application/json")
                self.send_response(200)
                self.send_header("Content-Type", ct)
                if streaming:
                    # No Content-Length — flush each NDJSON line as it arrives
                    self.end_headers()
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        self.wfile.write(line)
                        try:
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return   # client disconnected mid-stream — normal
                else:
                    body = resp.read()
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        except urllib.error.URLError as e:
            self._json_response(502, {"error": f"Ollama offline: {e.reason}"})
        except (BrokenPipeError, ConnectionResetError):
            pass   # client left — not an error
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── Proxy redirect — forwards 3xx from payments service to browser ───────
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    def _proxy_redirect(self, url: str):
        opener = urllib.request.build_opener(self._NoRedirect())
        try:
            with opener.open(url, timeout=15) as resp:
                # Payments returned 200 (shouldn't happen for checkout, but handle it)
                body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "text/html"))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location", "")
                self.send_response(303)
                self.send_header("Location", location)
                self.end_headers()
            else:
                self._json_response(e.code, {"error": f"Payment error: {e}"})
        except urllib.error.URLError as e:
            self._json_response(502, {"error": f"Payment service offline: {e.reason}"})

    # ── Serve a named page from client dir ────────────────────────────────────
    def _serve_page(self, filename: str):
        page = CLIENT_DIR / filename
        if not page.exists():
            self._json_response(404, {"error": f"{filename} not found"})
            return
        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── Proxy POST preserving all headers (for Stripe webhooks) ──────────────
    def _proxy_post_raw(self, url: str):
        length  = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
        }
        # Forward Stripe-Signature header for webhook verification
        sig = self.headers.get("stripe-signature") or self.headers.get("Stripe-Signature")
        if sig:
            headers["stripe-signature"] = sig
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json_response(502, {"error": str(e)})

    # ── JSON helper ───────────────────────────────────────────────────────────
    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── Logging: show API calls + errors, suppress static 200s ───────────────
    def log_message(self, fmt, *args):
        if not args:
            return
        status = str(args[1]) if len(args) > 1 else ""
        if self.path.startswith("/api/") or self.path == "/health":
            log.info(f"{self.command} {self.path} -> {status}")
        elif status not in ("200", "304"):
            log.warning(f"{self.command} {self.path} -> {status}")


class ReusableTCP(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True   # threads die when server dies


if __name__ == "__main__":
    os.chdir(CLIENT_DIR)

    # Quick startup probe
    ollama_up = False
    try:
        urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3)
        ollama_up = True
    except Exception:
        pass

    print(f"\n{'='*55}")
    print(f"  SovereignNation Client UI  v{VERSION}")
    print(f"{'='*55}")
    print(f"  Local  : http://localhost:{PORT}")
    print(f"  Health : http://localhost:{PORT}/health")
    print(f"  Ollama : {'ONLINE' if ollama_up else 'OFFLINE (start ollama serve)'}")
    print(f"  Proxy  : /api/* -> {OLLAMA}/api/*")
    print(f"{'='*55}\n")

    with ReusableTCP(("", PORT), SovereignHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")
