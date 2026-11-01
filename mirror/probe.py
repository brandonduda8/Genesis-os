#!/usr/bin/env python3
"""Trio probe for the vantage this runs on (WO §2: "each vantage publishes its own trio").

  python3 mirror/probe.py --vantage claude-cloud [--write]

Legs, reachability only. It never sends a credential, so a 401/403 from a model API still proves the lane is
REACHABLE, while a refused connection or timeout proves it is not.
  github   https://api.github.com
  package  https://registry.npmjs.org and https://pypi.org/simple/
  model    NVIDIA NIM, Groq, OpenRouter (any one reachable = ok; each recorded)
  docker   `docker info` succeeds on this host
--write stores the result as data/probes/<vantage>.json, the latest probe the router reads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {
    "github": ["https://api.github.com"],
    "package": ["https://registry.npmjs.org/", "https://pypi.org/simple/"],
    "model": ["https://integrate.api.nvidia.com/v1/models", "https://api.groq.com/openai/v1/models",
              "https://openrouter.ai/api/v1/models"],
}
ALL_MUST = {"github": True, "package": True, "model": False}  # model: any one lane suffices


def reach(url: str, timeout: float = 6.0) -> dict:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "genesis-mirror-probe/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"url": url, "ok": True, "status": r.status}
    except urllib.error.HTTPError as e:  # the server answered: reachable
        return {"url": url, "ok": e.code not in (407, 502, 503, 504), "status": e.code}
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        return {"url": url, "ok": False, "error": str(getattr(e, "reason", e))[:120]}


def docker_leg() -> dict:
    if not shutil.which("docker"):
        return {"ok": False, "error": "docker not installed"}
    p = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=20)
    return {"ok": p.returncode == 0, "version": p.stdout.strip() or None, "error": p.stderr.strip()[:120] or None}


def probe(vantage: str) -> dict:
    legs = {}
    for leg, urls in TARGETS.items():
        res = [reach(u) for u in urls]
        ok = all(r["ok"] for r in res) if ALL_MUST[leg] else any(r["ok"] for r in res)
        legs[leg] = {"ok": ok, "checks": res}
    legs["docker"] = docker_leg()
    return {"vantage": vantage, "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "host": socket.gethostname(), "legs": legs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vantage", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out = probe(a.vantage)
    if a.write:
        os.makedirs(os.path.join(HERE, "data", "probes"), exist_ok=True)
        with open(os.path.join(HERE, "data", "probes", f"{a.vantage}.json"), "w") as f:
            json.dump(out, f, indent=1)
            f.write("\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
