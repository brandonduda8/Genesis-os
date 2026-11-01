"""Emergency stop (WO-CLAUDE-MASTER-BUILD-001 Workstream 2). Two keys to stop, two keys to restart, two paths.

A command needs BOTH the founder's signature (the registry's founder key) AND an operator-class identity's signature.
Scope: one identity, a class, or the whole fleet. A STOP stays in force until a later RESTART whose scope covers it.

Path 1, the fabric: kind "stop"/"restart" envelopes, NOT encrypted (anyone must be able to verify them, and a broken
           session must never be able to block a stop).
Path 2, local: a stop directory (/run/genesis/estop or the GHOST state dir) that ghostd and every agent read every
           tick. It is written by `python3 -m genesis_fabric.stop write CMD.json --dir D`, by ghostd, or by a received
           fabric stop, so either path alone suffices. A stop that depends on the thing it stops is not a stop.

Restart ceremony: a RESTART must carry `inspected` (what the operator checked) and `order` (the restart sequence).
Agents not yet reached in `order` stay halted until the restart for them is issued. Every agent writes a receipt on halt
(where it stopped) and on resume (where it resumed from).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .crypto import FabricError, Keys, canon, verify
from .identity import Registry

SCOPES = ("identity", "class", "fleet")


class Halted(Exception):
    def __init__(self, cmd: Dict[str, Any]):
        super().__init__(f"HALTED by {cmd['kind']} {cmd['nonce'][:8]} ({cmd['scope']['type']}:"
                         f"{cmd['scope'].get('target')}): {cmd['reason']}")
        self.cmd = cmd


def command(kind: str, *, scope_type: str, target: Optional[str], reason: str, now: float,
            inspected: str = "", order: Optional[List[str]] = None) -> Dict[str, Any]:
    if kind not in ("stop", "restart") or scope_type not in SCOPES:
        raise FabricError("kind stop|restart, scope identity|class|fleet")
    if (scope_type == "fleet") != (target is None):
        raise FabricError("fleet scope has no target; other scopes need one")
    if not reason.strip():
        raise FabricError("a reason is required")
    cmd = {"v": 1, "kind": kind, "scope": {"type": scope_type, "target": target}, "reason": reason,
           "issued": int(now), "nonce": secrets.token_hex(16)}
    if kind == "restart":
        if not inspected.strip():
            raise FabricError("restart ceremony: state what was inspected before restarting")
        cmd["inspected"], cmd["order"] = inspected, list(order or [])
    return cmd


def sign(cmd: Dict[str, Any], *, founder: Keys, operator_name: str, operator: Keys) -> Dict[str, Any]:
    data = canon({"estop": cmd})
    return {"cmd": cmd, "founder_sig": founder.sign(data), "operator": operator_name, "operator_sig": operator.sign(data)}


def check(doc: Dict[str, Any], reg: Registry, now: float) -> Dict[str, Any]:
    cmd = doc.get("cmd") or {}
    data = canon({"estop": cmd})
    if not verify(reg.founder_pub, data, doc.get("founder_sig", "")):
        raise FabricError("estop: founder signature missing or invalid (two keys are required)")
    op = reg.get(doc.get("operator", ""), now)
    if op["class"] != "operator":
        raise FabricError(f"estop: {doc.get('operator')} is not an operator")
    if not verify(op["ed25519"], data, doc.get("operator_sig", "")):
        raise FabricError("estop: operator signature missing or invalid (two keys are required)")
    if cmd.get("issued", 0) > now + 300:
        raise FabricError("estop: issued in the future")
    if cmd.get("kind") == "restart" and not str(cmd.get("inspected", "")).strip():
        raise FabricError("estop: restart without an inspection statement")
    return cmd


def write(doc: Dict[str, Any], stop_dir: str) -> str:
    os.makedirs(stop_dir, mode=0o700, exist_ok=True)
    c = doc["cmd"]
    path = os.path.join(stop_dir, f"{c['issued']:012d}-{c['kind']}-{c['nonce']}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


class Guard:
    """Asked before every action: `guard.check()` raises Halted while any covering stop is in force."""

    def __init__(self, me: str, registry: Registry, stop_dir: str, clock=time.time):
        self.me, self.reg, self.dir, self.clock = me, registry, stop_dir, clock
        self.klass = registry.ids.get(me, {}).get("class")
        self.rejected: List[str] = []

    def ingest(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        cmd = check(doc, self.reg, self.clock())
        write(doc, self.dir)  # a fabric-received stop also persists locally: it survives restarts
        return cmd

    def on_envelope(self, env: Dict[str, Any]) -> Dict[str, Any]:
        cmd = self.ingest(env["hdr"]["command"])
        return {"from": env["from"], "kind": cmd["kind"], "cmd": cmd}

    def commands(self) -> List[Dict[str, Any]]:
        out, self.rejected = [], []
        if not os.path.isdir(self.dir):
            return out
        for f in sorted(os.listdir(self.dir)):
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.dir, f)) as fh:
                    out.append(check(json.load(fh), self.reg, self.clock()))
            except (FabricError, ValueError, KeyError) as e:
                self.rejected.append(f"{f}: {e}")  # a forged file never stops or restarts anything
        return out

    def _cls(self, name: str) -> Optional[str]:
        return self.reg.ids.get(name, {}).get("class")

    def _matches_me(self, scope: Dict[str, Any]) -> bool:
        t = scope["type"]
        return t == "fleet" or (t == "class" and scope["target"] == self.klass) or \
            (t == "identity" and scope["target"] == self.me)

    def _covers(self, r: Dict[str, Any], s: Dict[str, Any]) -> bool:
        rs, ss = r["scope"], s["scope"]
        if rs["type"] == "fleet":
            ok = True
        elif rs["type"] == "class":
            ok = ss["type"] == "class" and ss["target"] == rs["target"] or \
                ss["type"] == "identity" and self._cls(ss["target"]) == rs["target"]
        else:
            ok = ss["type"] == "identity" and ss["target"] == rs["target"]
        if ok and rs["type"] != "identity" and r.get("order") and self.me not in r["order"]:
            return False  # ceremony order: a broad restart only releases the agents it names
        return ok

    def state(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        cmds = self.commands()
        stops = [c for c in cmds if c["kind"] == "stop" and self._matches_me(c["scope"])]
        restarts = [c for c in cmds if c["kind"] == "restart"]
        for s in sorted(stops, key=lambda c: c["issued"]):
            if not any(r["issued"] > s["issued"] and self._covers(r, s) for r in restarts):
                return True, s
        return False, None

    def check(self) -> None:
        halted, cmd = self.state()
        if halted:
            raise Halted(cmd)


def broadcast(phone, doc: Dict[str, Any], targets: List[str]) -> Dict[str, List[str]]:
    """Path 1: send the two-key command to every target over the fabric (unencrypted, signed by the sender)."""
    from .envelope import make
    sent, failed = [], []
    for t in targets:
        env = make(phone.keys, sender=phone.me, to=t, kind=doc["cmd"]["kind"], hdr={"command": doc}, now=phone.clock())
        try:
            phone._push(env)
            sent.append(t)
        except FabricError as e:
            failed.append(f"{t}: {e}")
    return {"sent": sent, "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser(description="write a two-key stop/restart into a stop directory (path 2)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("command_json")
    w.add_argument("--dir", required=True)
    w.add_argument("--registry", required=True)
    s = sub.add_parser("status")
    s.add_argument("--me", required=True)
    s.add_argument("--dir", required=True)
    s.add_argument("--registry", required=True)
    a = ap.parse_args()
    with open(a.registry) as f:
        reg = Registry(json.load(f))
    if a.cmd == "write":
        with open(a.command_json) as f:
            doc = json.load(f)
        check(doc, reg, time.time())
        print(write(doc, a.dir))
        return 0
    g = Guard(a.me, reg, a.dir)
    halted, cmd = g.state()
    print(json.dumps({"me": a.me, "halted": halted, "by": cmd, "rejected_files": g.rejected}, indent=1))
    return 3 if halted else 0


if __name__ == "__main__":
    sys.exit(main())
