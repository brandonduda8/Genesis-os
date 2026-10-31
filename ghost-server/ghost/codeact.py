"""CodeAct execution (module 7) + deterministic verifiers.

A job may carry a small Python script that does a multi-tool chain in ONE execution. It runs:
  python3 -I -S -B script.py   in a fresh temp dir, scrubbed env, own process group, PR_SET_PDEATHSIG,
  rlimits CPU 30 s / AS 512 MB / FSIZE 16 MB / NOFILE 64, wall clock 60 s,
  with NO network via `unshare -rn` when available. Without network isolation the job is BLOCKED (fail closed).
The script's own claims are ignored. A result counts only when the job's fixed verifier passes:
  json_schema | sha256 | argv (separate sandboxed command, exit 0) | receipt | trio.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

WALL_S, CPU_S, AS_BYTES, FSIZE_BYTES, NOFILE = 60, 30, 512 << 20, 16 << 20, 64
SAFE_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
_NETNS: Optional[bool] = None


def netns_available() -> bool:
    global _NETNS
    if _NETNS is None:
        exe = shutil.which("unshare")
        try:
            _NETNS = bool(exe) and subprocess.run([exe, "-rn", "true"], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            _NETNS = False
    return _NETNS


def _preexec() -> None:  # runs in the child between fork and exec
    import resource
    os.setsid()
    try:
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG
    except OSError:
        pass
    for lim, val in ((resource.RLIMIT_CPU, CPU_S), (resource.RLIMIT_AS, AS_BYTES),
                     (resource.RLIMIT_FSIZE, FSIZE_BYTES), (resource.RLIMIT_NOFILE, NOFILE),
                     (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(lim, (val, val))


def _argv(cmd: List[str], isolate: bool) -> List[str]:
    return ([shutil.which("unshare") or "unshare", "-rn"] if isolate else []) + cmd


class Run:
    """A started sandboxed process; poll() until it returns a result."""

    def __init__(self, proc: subprocess.Popen, workdir: str, started: float, isolated: bool):
        self.proc, self.workdir, self.started, self.isolated = proc, workdir, started, isolated

    def poll(self) -> Optional[Dict[str, Any]]:
        rc = self.proc.poll()
        if rc is None and time.monotonic() - self.started < WALL_S:
            return None
        timed_out = rc is None
        if timed_out:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.proc.wait()
        out, err = self.proc.communicate()
        return {"rc": self.proc.returncode, "timed_out": timed_out, "stdout": out[-4000:], "stderr": err[-4000:],
                "seconds": round(time.monotonic() - self.started, 3), "isolated": self.isolated,
                "workdir": self.workdir}


def start(script: str, inputs: Dict[str, Any], *, allow_network: bool = False,
          base_dir: Optional[str] = None) -> Run:
    isolate = not allow_network
    if isolate and not netns_available():
        raise PermissionError("sandbox-no-netns")
    work = tempfile.mkdtemp(prefix="ghost-codeact-", dir=base_dir)
    os.makedirs(os.path.join(work, "out"))
    with open(os.path.join(work, "script.py"), "w") as f:
        f.write(script)
    with open(os.path.join(work, "input.json"), "w") as f:
        json.dump(inputs, f)
    proc = subprocess.Popen(_argv([sys.executable, "-I", "-S", "-B", "script.py"], isolate), cwd=work,
                            env={**SAFE_ENV, "HOME": work}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, preexec_fn=_preexec, close_fds=True)
    return Run(proc, work, time.monotonic(), isolate)


def run_blocking(script: str, inputs: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    r = start(script, inputs, **kw)
    while True:
        res = r.poll()
        if res is not None:
            return res
        time.sleep(0.05)


# ---------------------------------------------------------------------------------------------- verifiers
def _type_ok(v: Any, t: str) -> bool:
    return {"string": isinstance(v, str), "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool), "boolean": isinstance(v, bool),
            "array": isinstance(v, list), "object": isinstance(v, dict)}.get(t, False)


def check_schema(obj: Any, schema: Dict[str, Any]) -> List[str]:
    errs = []
    if schema.get("type") and not _type_ok(obj, schema["type"]):
        return [f"expected {schema['type']}"]
    if isinstance(obj, dict):
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"missing {k}")
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                errs += [f"{k}: {e}" for e in check_schema(obj[k], sub)]
    if "const" in schema and obj != schema["const"]:
        errs.append(f"expected const {schema['const']!r}")
    return errs


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _inside(root: str, path: str) -> bool:
    root, path = os.path.realpath(root), os.path.realpath(path)
    return path == root or path.startswith(root + os.sep)


def verify(verifier: Dict[str, Any], *, job_id: str, workdir: Optional[str] = None,
           receipts_root: Optional[str] = None, receipt_path: Optional[str] = None,
           trio_healed: Optional[Callable[[str], bool]] = None) -> Tuple[bool, str]:
    """Deterministic only. Returns (passed, detail). Unknown verifier kinds fail."""
    kind = verifier.get("kind")
    try:
        if kind == "json_schema":
            p = os.path.join(workdir or "", "out", "result.json")
            if not os.path.isfile(p):
                return False, "out/result.json missing"
            errs = check_schema(json.load(open(p)), verifier.get("schema", {}))
            return (not errs), ("schema ok" if not errs else "; ".join(errs[:5]))
        if kind == "sha256":
            p = os.path.join(workdir or "", verifier["artifact"])
            if not _inside(workdir or "", p) or not os.path.isfile(p):
                return False, "artifact missing or outside workdir"
            got = _sha(p)
            return got == verifier["expect"], f"sha256={got}"
        if kind == "argv":
            if "script" not in verifier:
                return False, "argv verifier needs an inline 'script' (runs in its own sandbox)"
            outputs: Dict[str, str] = {}
            out_dir = os.path.join(workdir or "", "out")
            for name in sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []:
                fp = os.path.join(out_dir, name)
                if os.path.isfile(fp) and os.path.getsize(fp) <= 65536:
                    outputs[name] = open(fp, encoding="utf-8", errors="replace").read()
            # a separate sandbox; it sees copies of the job's outputs, never the job's own verdict
            res = run_blocking(verifier["script"], {"job_id": job_id, "outputs": outputs}, allow_network=False)
            return res["rc"] == 0 and not res["timed_out"], f"verifier rc={res['rc']}"
        if kind == "receipt":
            if not receipt_path or not receipts_root:
                return False, "no receipt path supplied"
            p = os.path.join(receipts_root, receipt_path)
            if not _inside(receipts_root, p) or not os.path.isfile(p):
                return False, f"receipt {receipt_path} not found inside receipts root"
            text = open(p, encoding="utf-8", errors="replace").read()
            must = verifier.get("must_mention", job_id)
            if must not in text:
                return False, f"receipt does not mention {must}"
            return True, f"receipt sha256={_sha(p)}"
        if kind == "trio":
            ok = bool(trio_healed and trio_healed(verifier.get("door", "")))
            return ok, "door healed" if ok else "door not healed"
    except (OSError, ValueError, KeyError, PermissionError) as exc:
        return False, f"verifier error: {type(exc).__name__}: {exc}"
    return False, f"unknown verifier kind {kind!r}"
