"""Legacy file-queue reader + migration (P1 reader, P5 migration).

The ghost/queue/ files are READ, never written. Each import:
  * derives the job ID deterministically from the file (JSON `id`, or the `Q-NNN` filename prefix for .md);
  * records the file path and its SHA-256 (plus the git blob, when available) as the lineage source;
  * takes structured `requires` / lane / assignee ONLY from the reviewed ID-keyed config (never inferred from prose);
  * classifies the level on title + command (not on fence notes); Level C jobs enter BLOCKED and escalate.
Re-running is idempotent: an unchanged file is skipped; a changed file adds a lineage note and is reported, but the
job's state is not overwritten.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from . import gates
from .registry import BLOCKED, DEAD, QUEUED, Registry

MD_ID = re.compile(r"^(?:GHOST-)?Q-(\d{3,})\b")
MD_FIELD = lambda name: re.compile(rf"\*\*{name}:\*\*\s*(.+)", re.I)  # noqa: E731
LEGACY_STATUS = {"QUEUED": QUEUED, "DEAD-LETTER": DEAD}


def status_token(status: str) -> str:
    """Leading status word of a legacy status ("QUEUED — work order written …" -> "QUEUED"). Prose is kept in spec."""
    m = re.match(r"\s*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)", status or "")
    return m.group(1) if m else ""


def _git_blob(path: str) -> str:
    try:
        out = subprocess.run(["git", "hash-object", path], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def read_legacy(path: str) -> Dict[str, Any]:
    raw = open(path, "rb").read()
    base = os.path.basename(path)
    if path.endswith(".json"):
        d = json.loads(raw)
        rec = {"job_id": d["id"], "title": d["title"], "target_host": d.get("target_host", ""),
               "requires_path": d.get("requires_path", ""), "command_or_ref": d.get("command_or_ref", ""),
               "fence_notes": d.get("fence_notes", ""), "queued_at": d.get("queued_at", ""),
               "status": d.get("status", "QUEUED"), "receipt_target": d.get("receipt_target", "")}
    else:
        text = raw.decode("utf-8")
        m = MD_ID.match(base)
        if not m:
            raise ValueError(f"{base}: cannot derive a deterministic job id")
        head = text.splitlines()[0].lstrip("# ").strip() if text else base
        get = lambda n: (MD_FIELD(n).search(text).group(1).strip() if MD_FIELD(n).search(text) else "")  # noqa: E731
        status = get("Status").split(".")[0].split()[0] if get("Status") else "QUEUED"
        rec = {"job_id": f"GHOST-Q-{m.group(1)}", "title": head, "target_host": "",
               "requires_path": get("requires_path"), "command_or_ref": get("Job"), "fence_notes": "",
               "queued_at": "", "status": status.strip("*"), "receipt_target": ""}
    rec["source_path"], rec["source_sha256"], rec["git_blob"] = path, hashlib.sha256(raw).hexdigest(), _git_blob(path)
    return rec


def _human_only(requires: List[Any]) -> Optional[str]:
    """If some AND-term can never be satisfied by the server (all-human), return its gate name."""
    for term in requires:
        options = term["any"] if isinstance(term, dict) else [term]
        if all(isinstance(o, str) and o.startswith("human:") for o in options):
            return options[0]
    return None


def migrate(reg: Registry, queue_dir: str, mapping_path: str, *, actor: str, gate: Optional[gates.Gate] = None,
            repo_root: Optional[str] = None) -> Dict[str, List[str]]:
    mapping = json.load(open(mapping_path))
    report: Dict[str, List[str]] = {"created": [], "unchanged": [], "changed": [], "blocked": [], "level_c": []}
    files = sorted(glob.glob(os.path.join(queue_dir, "*.json")) + glob.glob(os.path.join(queue_dir, "Q-*.md")))
    report["duplicate_ids"] = []
    seen: Dict[str, str] = {}
    for path in files:
        rec = read_legacy(path)
        jid = rec["job_id"]
        if jid in seen:  # one ID, one file: a second file never overwrites or merges into the first
            report["duplicate_ids"].append(f"{jid}:{os.path.basename(path)} (kept {os.path.basename(seen[jid])})")
            reg.ledger("legacy_duplicate_id", actor, {"job_id": jid, "kept": seen[jid], "refused": path}, jid)
            continue
        seen[jid] = path
        rel = os.path.relpath(path, repo_root) if repo_root else path
        source = f"{rel}@sha256:{rec['source_sha256']}" + (f"@git:{rec['git_blob']}" if rec["git_blob"] else "")
        existing = reg.get(jid)
        if existing:
            if existing["spec"].get("legacy_sha256") == rec["source_sha256"]:
                report["unchanged"].append(jid)
            else:
                reg.note_lineage(jid, actor, "legacy_file_changed", source=source,
                                 note="legacy file differs from imported copy; state NOT overwritten — review")
                report["changed"].append(jid)
            continue
        m = mapping.get(jid)
        level = gates.classify("release_envelope", f"{rec['title']} {rec['command_or_ref']}")
        job = {"job_id": jid, "title": rec["title"], "lane": (m or {}).get("lane", "ops"), "executor": "manual",
               "assignee": (m or {}).get("assignee", ""), "target_host": rec["target_host"],
               "requires": (m or {}).get("requires", []), "level": level, "receipt_target": rec["receipt_target"],
               "verifier": {"kind": "receipt", "path_hint": rec["receipt_target"], "must_mention": jid},
               "spec": {"command_or_ref": rec["command_or_ref"], "fence_notes": rec["fence_notes"],
                        "requires_path_text": rec["requires_path"], "legacy_status": rec["status"],
                        "legacy_queued_at": rec["queued_at"], "legacy_source": rel,
                        "legacy_sha256": rec["source_sha256"]}}
        token = status_token(rec["status"])
        state, reason = LEGACY_STATUS.get(token, QUEUED), ""
        if token not in LEGACY_STATUS:  # nothing is DONE (or ACTIVE) because a file says so: it waits, visibly
            state, reason = BLOCKED, f"legacy-status-{(token or 'prose').lower()}-unverified"
        elif level == "C":
            state, reason = BLOCKED, "level-c-brandon"
        elif m is None:
            state, reason = BLOCKED, "requires-unmapped"
        elif _human_only(job["requires"]):
            state, reason = BLOCKED, _human_only(job["requires"])
        reg.add_job(job, actor=actor, source=source, state=state, blocked_reason=reason, transform="legacy_import")
        report["created"].append(jid)
        if state == BLOCKED:
            report["blocked"].append(f"{jid}:{reason}")
        if level == "C":
            report["level_c"].append(jid)
            if gate:
                gate._escalate("release_envelope", jid, "legacy job text classified Level C", actor)
    reg.ledger("legacy_migration", actor, dict({k: len(v) for k, v in report.items()}, queue_dir=queue_dir))
    return report
