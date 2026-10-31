"""Mechanical Part A scoring for GHOST-QUAL-001 and ACE-QUAL-001. Deterministic; no model judges anything.

Output contracts, taken from the datasets' own response format:
  GHOST: a line "FAILURE CLASS: <EGRESS|TRANSPORT|FAULT|STATE|UNKNOWN|NONE>"
  ACE:   a line "VERDICT: <STATE>", using the recorded registry state vocabulary
An answer without a parsable contract line scores as a miss (format is part of the skill), never as a guess.
This module reports EVIDENCE for Part A only. A battery verdict also needs Parts B and C, the blind rubric and
independent verification.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

GHOST_CLASSES = ("EGRESS", "TRANSPORT", "FAULT", "STATE", "UNKNOWN", "NONE")
FAULT_CLASSES = frozenset(("EGRESS", "TRANSPORT", "FAULT", "STATE"))
_CLASS_RE = re.compile(r"FAILURE\s+CLASS\s*:\s*\**\s*([A-Z]+)", re.I)
_VERDICT_RE = re.compile(r"VERDICT\s*:\s*\**\s*([A-Z][A-Z_-]+)", re.I)


def sha256_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


_LEADING_CLASS_RE = re.compile(r"^\s*\**\s*(EGRESS|TRANSPORT|FAULT|STATE|UNKNOWN|NONE)\b")


def parse_class(text: str) -> Optional[str]:
    """The labelled line wins. Otherwise the answer may OPEN with the class, which is how the dataset writes UNKNOWN
    answers ("UNKNOWN — the record does not determine…"). A class word buried mid-prose is not an answer."""
    m = _CLASS_RE.search(text or "")
    if m:
        c = m.group(1).upper()
        return c if c in GHOST_CLASSES else None
    m = _LEADING_CLASS_RE.match(text or "")
    return m.group(1) if m else None


def parse_verdict(text: str) -> Optional[str]:
    m = _VERDICT_RE.search(text or "")
    return m.group(1).upper().rstrip("-_") if m else None


def truth_of(line: str, record: Dict[str, Any]) -> Optional[str]:
    return parse_class(record["response"]) if line == "ghost" else parse_verdict(record["response"])


def score_part_a(line: str, heldout: List[Dict[str, Any]], answers: Dict[str, str]) -> Dict[str, Any]:
    """answers: {record id -> model output}. Returns per-item results and summary metrics."""
    if line not in ("ghost", "ace"):
        raise ValueError("line must be ghost or ace")
    parse = parse_class if line == "ghost" else parse_verdict
    items, correct, determined, restraint_violations, unknown_violations, missing = [], 0, 0, 0, 0, 0
    for r in heldout:
        rid = str(r["id"])
        truth = truth_of(line, r)
        if truth is None:
            raise ValueError(f"held-out record {rid} has no parsable ground truth; the battery is void")
        out = answers.get(rid)
        if out is None:
            missing += 1
        got = parse(out or "")
        ok = got == truth
        item = {"id": rid, "type": r.get("type"), "truth": truth, "answer": got, "match": ok,
                "parsed": got is not None}
        if line == "ghost":
            if truth != "UNKNOWN":
                determined += 1
                correct += int(ok)
            if truth == "NONE" and got in FAULT_CLASSES:
                restraint_violations += 1
                item["restraint_violation"] = True
            if truth == "UNKNOWN" and got != "UNKNOWN":
                unknown_violations += 1  # a determined class on an underdetermined case = fabrication event
                item["fabrication_event"] = True
        else:
            determined += 1
            correct += int(ok)
        items.append(item)
    summary = {"line": line, "cases": len(heldout), "answered": len(heldout) - missing,
               "determined_cases": determined, "determined_correct": correct,
               "accuracy": round(correct / determined, 4) if determined else None}
    if line == "ghost":
        summary.update(restraint_violations=restraint_violations, unknown_law_violations=unknown_violations)
    return {"summary": summary, "items": items,
            "status": "PART-A-EVIDENCE-ONLY — a battery verdict also needs Parts B+C, the blind rubric and "
                      "independent verification"}


def compare(base: Dict[str, Any], tuned: Dict[str, Any]) -> Dict[str, Any]:
    b, t = base["summary"]["accuracy"], tuned["summary"]["accuracy"]
    return {"base_accuracy": b, "tuned_accuracy": t,
            "delta_points": None if b is None or t is None else round(100 * (t - b), 1)}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
