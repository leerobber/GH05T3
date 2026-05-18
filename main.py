import os
import sys
import subprocess
import time
import signal
import threading

BASE = os.path.dirname(os.path.abspath(__file__))

def log(msg):
    print(f"[GH05T3] {msg}")

def run(cmd, name):
    return subprocess.Popen(
        cmd,
        cwd=BASE,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

class Service:
    def __init__(self, name, cmd):
        self.name = name
        self.cmd = cmd
        self.process = None

    def start(self):
        log(f"Starting {self.name}")
        self.process = run(self.cmd, self.name)

    def alive(self):
        return self.process and self.process.poll() is None

    def restart(self):
        log(f"Restarting {self.name}")
        self.start()

    def stop(self):
        if self.process:
            log(f"Stopping {self.name}")
            self.process.terminate()

class GH05T3:
    def __init__(self):
        self.services = []
        self.running = True

    def setup(self):
        python = sys.executable

        self.services = [
            Service("mongo", "mongod --dbpath mongo-data --port 27017 --bind_ip 127.0.0.1"),
            Service("backend", f'"{python}" -m backend.server'),
            Service("gateway", f'"{python}" -m backend.gateway_v3'),
            Service("frontend", f'"{python}" -m http.server 3210 --directory frontend/build'),
            Service("whisper", f'"{python}" whisper_listener.py'),
        ]

    def start_all(self):
        for s in self.services:
            try:
                s.start()
                time.sleep(1)
            except Exception as e:
                log(f"Failed {s.name}: {e}")

    def monitor(self):
        while self.running:
            for s in self.services:
                if not s.alive():
                    log(f"{s.name} died → restarting")
                    s.restart()
            time.sleep(5)

    def shutdown(self, *_):
        log("Shutting down system...")
        self.running = False
        for s in self.services:
            s.stop()
        sys.exit(0)

    def run(self):
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        log("Launching GH05T3 PRODUCTION MODE")
        self.setup()
        self.start_all()

        threading.Thread(target=self.monitor, daemon=True).start()

        log("System running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    GH05T3().run()
