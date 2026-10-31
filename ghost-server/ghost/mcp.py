"""MCP (stdio JSON-RPC 2.0) for tool/resource access inside the runtime. READ-ONLY by construction.

Exposes ghost_status, ghost_provenance, ghost_board, ghost_doors, ghost_ledger_verify. There is no mutating tool:
state changes go through gates.Gate (identity + scope + signed receipt) and never through MCP. Cross-machine
delegation uses A2A envelopes (envelope.py), not MCP. The two layers stay separate.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from . import metrics
from .registry import Registry, display_state

PROTOCOL = "2025-06-18"
TOOLS = {
    "ghost_status": ("Jobs by id with state, lane and assignee", {}),
    "ghost_provenance": ("Full lineage/attempts/artifacts/ledger history of one job",
                         {"job_id": {"type": "string", "pattern": "^GHOST-Q-[0-9]{3,}$"}}),
    "ghost_board": ("The STEM scorecard as text", {}),
    "ghost_doors": ("Latest door trio verdicts and breaker states", {}),
    "ghost_ledger_verify": ("Re-hash the evidence ledger chain", {}),
}


def call(reg: Registry, name: str, args: Dict[str, Any]) -> Any:
    if name == "ghost_status":
        return [{"job_id": j["job_id"], "state": display_state(j), "lane": j["lane"], "assignee": j["assignee"],
                 "title": j["title"]} for j in reg.jobs()]
    if name == "ghost_provenance":
        jid = str(args.get("job_id", ""))
        if not reg.get(jid):
            raise ValueError(f"unknown job {jid}")
        return reg.provenance(jid)
    if name == "ghost_board":
        return metrics.render_text(metrics.scorecard(reg))
    if name == "ghost_doors":
        return reg.door_states()
    if name == "ghost_ledger_verify":
        return reg.verify_ledger()
    raise ValueError(f"unknown tool {name}")


def handle(reg: Registry, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:
        return None  # notification
    try:
        if method == "initialize":
            result: Any = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                           "serverInfo": {"name": "ghost-server", "version": "2.0.0"}}
        elif method == "tools/list":
            result = {"tools": [{"name": n, "description": d,
                                 "inputSchema": {"type": "object", "properties": p, "required": list(p)},
                                 "annotations": {"readOnlyHint": True}} for n, (d, p) in TOOLS.items()]}
        elif method == "tools/call":
            p = msg.get("params", {})
            out = call(reg, p.get("name", ""), p.get("arguments") or {})
            result = {"content": [{"type": "text", "text": out if isinstance(out, str) else json.dumps(out, default=str)}]}
        elif method == "ping":
            result = {}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": mid, "result": {"isError": True,
                                                        "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}]}}


def serve(reg: Registry, stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            stdout.flush()
            continue
        resp = handle(reg, msg)
        if resp is not None:
            stdout.write(json.dumps(resp, default=str) + "\n")
            stdout.flush()
