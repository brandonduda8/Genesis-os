#!/usr/bin/env python3
"""Build the Cody training dataset v1 (WO-CODY-REAL-SOFTWARE-2026-10-31, Stream A step 1).

Design: every record traces to a real file on disk (the `source` field).
Transformations are mechanical only: section splitting, verbatim excerpting,
WO->receipt pairing, code/test pairing. No facts are invented; the only
authored strings are fixed question framings in QA records, whose answers are
verbatim source text.

Record shapes:
  {"type":"qa",        "instruction":..., "response":..., "source":..., "detail":...}
  {"type":"doc",       "text":..., "source":..., "detail":...}
  {"type":"code_pair", "instruction":..., "response":..., "source":..., "detail":...}
  {"type":"code",      "text":..., "source":..., "detail":...}

Credential rule: files matching *secret*, *.env, credentials*, *.pem, *.key are
never opened. Emitted text is also scanned for credential shapes; a hit drops
the record and increments the drop counter reported in MANIFEST.md.
"""
import json, re, sys
from pathlib import Path

HOME = Path.home()
G = HOME / "workspace/genesis-os"
OUT = G / "training/datasets/cody-v1/corpus"
MAXCH = 6000          # per-record text cap (docs/code chunks)
PAIR_MAX = 16000      # intact code+test pair cap
DROP_PATTERNS = [r"nvapi-[A-Za-z0-9]", r"ghp_[A-Za-z0-9]", r"sk-[A-Za-z0-9]{20,}",
                 r"BEGIN [A-Z ]*PRIVATE KEY", r"hsurr:", r"AKIA[0-9A-Z]{16}"]
SKIP_NAME = re.compile(r"secret|\.env|credential|\.pem|\.key", re.I)

stats = {"dropped_credential_shape": 0}
counters = {}

def rel(p: Path) -> str:
    try:
        return str(p.relative_to(HOME / "workspace"))
    except ValueError:
        return str(p)

def safe_read(p: Path) -> str | None:
    if SKIP_NAME.search(p.name):
        stats["skipped_credential_file"] = stats.get("skipped_credential_file", 0) + 1
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

def clean(rec: dict) -> dict | None:
    blob = json.dumps(rec, ensure_ascii=False)
    for pat in DROP_PATTERNS:
        if re.search(pat, blob):
            stats["dropped_credential_shape"] += 1
            return None
    return rec

class Sink:
    def __init__(self, name):
        self.f = open(OUT / name, "w", encoding="utf-8")
        self.n = 0
    def add(self, rec):
        rec = clean(rec)
        if rec is None:
            return
        rec["id"] = f"cody-v1-{self.n + 1:05d}"
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.f.flush()
        self.n += 1
        counters[rec["source"]] = counters.get(rec["source"], 0) + 1
    def close(self):
        self.f.close()

def split_md(text: str, cap: int = MAXCH):
    """Split markdown at ## / ### headers; hard-split oversize sections."""
    parts, cur, cur_h = [], [], "(preamble)"
    for line in text.splitlines():
        if re.match(r"^#{2,3} ", line) and cur:
            parts.append((cur_h, "\n".join(cur)))
            cur, cur_h = [], line.strip("# ").strip()
        cur.append(line)
    if cur:
        parts.append((cur_h, "\n".join(cur)))
    out = []
    for h, body in parts:
        body = body.strip()
        while len(body) > cap:
            cut = body.rfind("\n", 0, cap)
            if cut < cap // 2:
                cut = cap
            out.append((h, body[:cut]))
            body = body[cut:].lstrip("\n")
        if body:
            out.append((h, body))
    return out

def split_code(text: str, cap: int = MAXCH):
    """Split a Python file at top-level def/class boundaries."""
    lines = text.splitlines()
    bounds = [i for i, l in enumerate(lines) if re.match(r"^(async def |def |class )", l)]
    if not bounds:
        chunks, body = [], text
        while len(body) > cap:
            cut = body.rfind("\n", 0, cap)
            chunks.append(body[:cut if cut > cap // 2 else cap])
            body = body[cut if cut > cap // 2 else cap:].lstrip("\n")
        return [(None, c) for c in chunks if c.strip()] or [(None, text)]
    chunks, start = [], 0
    for b in bounds + [len(lines)]:
        seg = "\n".join(lines[start:b])
        if seg.strip():
            m = re.match(r"^(?:async def |def |class )(\w+)", lines[b - 1] if b else "")
            chunks.append((None, seg))
        start = b
    out = []
    for _, c in chunks:
        while len(c) > cap:
            cut = c.rfind("\n", 0, cap)
            out.append(c[:cut if cut > cap // 2 else cap])
            c = c[cut if cut > cap // 2 else cap:].lstrip("\n")
        out.append(c)
    return [(None, c) for c in out if c.strip()]


# ---------------------------------------------------------------- docs
DOC_FILES = [
    G / "cody/CHARTER.md",
    G / "cody/README.md",
    G / "cody/ARCHITECTURE.md",
    G / "cody/WORK_ORDER_TEMPLATE.md",
    G / "cody/CLAUDE_CREDIT_POLICY.md",
    G / "cody/CODY_VISION_2026-10-24.md",
    G / "ENGINEERING_STANDARD.md",
    G / "war-room/WO-CODY-P0-EXECUTE-001.md",
    G / "war-room/WO-OPENCODE-MASTER-2026-10-31.md",
    G / "war-room/WO-CODY-REAL-SOFTWARE-2026-10-31.md",
    G / "war-room/CODY_V1_RECEIPT_2026-10-24.md",
    G / "war-room/CODY_PHASE0_RECEIPT_2026-10-24.md",
    G / "war-room/CODY_CATCHUP_RECEIPT_2026-10-24.md",
    G / "war-room/WO-OPENCODE-MASTER_RECEIPT_2026-10-26.md",
    G / "war-room/OPENCODE2_PILOT_RECEIPT_2026-10-24.md",
    G / "cody/missions/CODY-QUAL-001/WO_SPEC.md",
    G / "master-runtime/README.md",
    G / "training-sdk/README.md",
    G / "training-sdk/SMOKE.md",
    G / "pay/README.md",
    G / "pay/genesis_vault/README.md",
]

def build_docs(sink: Sink):
    for p in DOC_FILES:
        text = safe_read(p)
        if text is None:
            print(f"  docs: MISSING/SKIPPED {rel(p)}", file=sys.stderr)
            continue
        for h, chunk in split_md(text):
            sink.add({"type": "doc", "text": chunk, "source": rel(p),
                      "detail": f"section: {h}"})
    # MEMORY.md: bounded operative-rule sections only (heading -> next heading)
    mem = safe_read(HOME / "MEMORY.md")
    if mem:
        wanted = ["THE RESET — COMPLETION STANDARD", "DONE — SHARPENED AGAIN",
                  "TRAINING FENCE LIFTED"]
        lines = mem.splitlines()
        heads = [i for i, l in enumerate(lines) if l.startswith("## ")]
        for idx, start in enumerate(heads):
            end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
            title = lines[start][3:]
            if any(w in title for w in wanted):
                body = "\n".join(lines[start:end])[:3500]
                sink.add({"type": "doc", "text": body, "source": "MEMORY.md",
                          "detail": f"section: {title}"})
    # AGENTS.md conventions: section chunks, each truncated
    ag = safe_read(HOME / "AGENTS.md")
    if ag:
        for h, chunk in split_md(ag, cap=2500):
            sink.add({"type": "doc", "text": chunk, "source": "AGENTS.md",
                      "detail": f"section: {h}"})

# ---------------------------------------------------------------- QA
def build_qa(sink: Sink):
    # Engineering Standard: one QA per numbered rule (answers verbatim)
    std = safe_read(G / "ENGINEERING_STANDARD.md")
    if std:
        m = re.search(r"## The one rule.*?(?=\n## )", std, re.S)
        if m:
            sink.add({"type": "qa",
                      "instruction": "According to the Genesis Engineering Standard, what is the one rule everything hangs on — when may work be called DONE?",
                      "response": m.group(0).split("\n", 1)[1].strip(),
                      "source": rel(G / "ENGINEERING_STANDARD.md"),
                      "detail": "section: The one rule everything hangs on"})
        for mm in re.finditer(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*?)(?=^\d+\.\s+\*\*|^## |\Z)",
                              std, re.S | re.M):
            num, title, rest = mm.group(1), mm.group(2), mm.group(3).strip()
            sink.add({"type": "qa",
                      "instruction": f"According to the Genesis Engineering Standard, rule {num}: what does '{title}' require?",
                      "response": f"**{title}** {rest}",
                      "source": rel(G / "ENGINEERING_STANDARD.md"),
                      "detail": f"rule {num}: {title}"})
    # Charter: section-level QA, answers verbatim
    ch = safe_read(G / "cody/CHARTER.md")
    if ch:
        questions = {
            "1. Mission": "What is Cody's mission, and what are its three non-negotiables?",
            "1.1 P0 success criterion": "What is Cody's P0 success criterion (WO-CODY-P0-EXECUTE-001), verbatim?",
            "2. What Cody is": "What is Cody, and what is Cody not?",
            "3. Seats": "What are Cody's seats, who holds each by default, and what does each never do?",
            "4. Operating principles": "What are Cody's operating principles?",
            "Quality gates": "What are Cody's charter-level quality gates (§4.1)?",
            "5. Authority fences": "What are Cody's authority fences (Platinum Levels A, B, C)?",
            "6. Claude-conservation law": "What is Cody's Claude-conservation law?",
            "BLOCKED vocabulary": "What is Cody's exact BLOCKED vocabulary (§7.1), and what must each label state?",
            "7. Accountability": "Who is accountable for Cody's output, and in what format does Cody report?",
        }
        for h, chunk in split_md(ch, cap=9000):
            for key, q in questions.items():
                if h.startswith(key) or key in h:
                    sink.add({"type": "qa", "instruction": q,
                              "response": chunk[:6500],
                              "source": rel(G / "cody/CHARTER.md"),
                              "detail": f"section: {h}"})
    # WO -> receipt gold chains: full work order in, filed receipt out
    chains = [
        (G / "war-room/WO-CODY-P0-EXECUTE-001.md", G / "war-room/CODY_V1_RECEIPT_2026-10-24.md"),
        (G / "war-room/WO-OPENCODE-MASTER-2026-10-26.md", G / "war-room/WO-OPENCODE-MASTER_RECEIPT_2026-10-26.md"),
    ]
    for wo_p, rc_p in chains:
        wo, rc = safe_read(wo_p), safe_read(rc_p)
        if wo and rc:
            sink.add({"type": "qa",
                      "instruction": ("You are Cody, Genesis's engineering department. Execute this "
                                      "work order under the charter and the Engineering Standard, "
                                      "then file the receipt.\n\n" + wo[:5000]),
                      "response": rc[:6500],
                      "source": f"{rel(wo_p)} -> {rel(rc_p)}",
                      "detail": "gold chain: work order -> filed receipt"})
    # Per-section receipt QA: verdict sections of each receipt, verbatim
    for rp in [G / "war-room/CODY_V1_RECEIPT_2026-10-24.md",
               G / "war-room/CODY_PHASE0_RECEIPT_2026-10-24.md",
               G / "war-room/CODY_CATCHUP_RECEIPT_2026-10-24.md",
               G / "war-room/WO-OPENCODE-MASTER_RECEIPT_2026-10-26.md"]:
        text = safe_read(rp)
        if not text:
            continue
        for h, chunk in split_md(text, cap=6500):
            if h.upper().startswith(("VERIFIED", "BUILT", "STAGED", "BLOCKED", "NEEDS APPROVAL")):
                sink.add({"type": "qa",
                          "instruction": f"In the receipt {rp.name}, what is recorded under '{h}'? Reproduce it exactly.",
                          "response": chunk,
                          "source": rel(rp), "detail": f"receipt section: {h}"})


# ---------------------------------------------------------------- code
# (module, [test files]) — pairs ship intact when they fit PAIR_MAX,
# otherwise both sides are chunked as `code` records cross-referenced
# via `detail`. Modules with no tests ship as chunked `code` records.
PAIRS = [
    (G / "ghost/egress-router/router.py", [G / "ghost/egress-router/tests/test_router.py"]),
    (G / "pay/genesis_pay/core.py", [G / "pay/tests/test_genesis_pay.py"]),
    (G / "pay/genesis_pay/paylinks.py", [G / "pay/tests/test_paylinks.py"]),
    (G / "pay/genesis_vault/ledger.py", [G / "pay/genesis_vault/tests/test_vault.py"]),
    (G / "pay/genesis_vault/rules.py", [G / "pay/genesis_vault/tests/test_vault_phase2.py"]),
    (G / "pay/genesis_vault/board.py", [G / "pay/genesis_vault/tests/test_balance_restatement.py"]),
    (G / "pay/tools/verify_pay_page.py", [G / "pay/tools/test_verify_pay_page.py"]),
]
UNPAIRED_CODE = [
    G / "master-runtime/master_runtime.py",
    G / "pay/genesis_pay/errors.py",
    G / "pay/genesis_pay/__init__.py",
    G / "pay/genesis_vault/cli.py",
    G / "pay/genesis_vault/parking.py",
    G / "pay/genesis_vault/__main__.py",
    G / "pay/tests/test_argon_acceptance.py",
    G / "training-sdk/gensdk/ledger.py",
    G / "training-sdk/gensdk/jobspec.py",
    G / "training-sdk/gensdk/policy.py",
    G / "training-sdk/gensdk/util.py",
    G / "training-sdk/gensdk/cli.py",
    G / "training-sdk/gensdk/providers/base.py",
    G / "training-sdk/gensdk/providers/kaggle.py",
    G / "training-sdk/gensdk/providers/colab.py",
    G / "training-sdk/gensdk/providers/local_s1.py",
    G / "cody/qualify_harness.py",
    G / "cody/workers/run_call.py",
]

def purpose_of(text: str) -> str:
    m = re.search(r'"""(.+?)"""', text, re.S)
    if m:
        first = " ".join(m.group(1).split())[:160]
        if first:
            return first
    for line in text.splitlines():
        if line.startswith("#") and len(line.strip("# ")) > 8:
            return line.strip("# ")[:160]
    return "Genesis fleet module"

def emit_code_chunks(sink: Sink, p: Path, text: str, note: str):
    for i, (_, chunk) in enumerate(split_code(text), 1):
        sink.add({"type": "code",
                  "text": f"# {rel(p)} — {note} (chunk {i})\n{chunk}",
                  "source": rel(p), "detail": note})

def build_code(sink: Sink):
    for mod, tests in PAIRS:
        mt = safe_read(mod)
        if mt is None:
            continue
        tt = "\n".join(t for t in (safe_read(x) for x in tests) if t)
        test_names = ", ".join(rel(x) for x in tests)
        if len(mt) + len(tt) <= PAIR_MAX and tt:
            sink.add({"type": "code_pair",
                      "instruction": (f"Implement the Genesis module `{rel(mod)}` — {purpose_of(mt)} "
                                      f"Ship it with its tests ({test_names}). Tests are the contract: "
                                      "the module is incomplete until they pass."),
                      "response": f"# {rel(mod)}\n{mt}\n\n# ===== TESTS: {test_names} =====\n{tt}",
                      "source": rel(mod), "detail": f"tests: {test_names}"})
        else:
            emit_code_chunks(sink, mod, mt, f"module; tests in {test_names} (oversize pair, chunked)")
            for x in tests:
                t = safe_read(x)
                if t:
                    emit_code_chunks(sink, x, t, f"tests for {rel(mod)} (oversize pair, chunked)")
    for p in UNPAIRED_CODE:
        text = safe_read(p)
        if text is None:
            continue
        emit_code_chunks(sink, p, text, "module (no paired test file in tree)")

# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sinks = {}
    for name, builder in [("docs.jsonl", build_docs), ("qa.jsonl", build_qa),
                          ("code.jsonl", build_code)]:
        s = Sink(name)
        builder(s)
        s.close()
        sinks[name] = s.n
        print(f"{name}: {s.n} records")
    # merged corpus
    total = 0
    with open(OUT / "cody-v1.jsonl", "w", encoding="utf-8") as merged:
        for name in ["qa.jsonl", "docs.jsonl", "code.jsonl"]:
            for line in open(OUT / name, encoding="utf-8"):
                merged.write(line)
                total += 1
    print(f"TOTAL: {total} records")
    print(json.dumps({"by_file": sinks, "stats": stats,
                      "per_source": dict(sorted(counters.items()))}, indent=1))

if __name__ == "__main__":
    main()
