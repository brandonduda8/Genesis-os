#!/usr/bin/env python3
"""ACE Training Dataset v1 builder (QUEUE row #9).

Mirrors the Cody v1 pattern: every record provenanced (`source` + `detail`),
mechanical transforms only, credential/PII-shaped content excluded by rule,
held-out set frozen + hashed BEFORE the training split is written.
Re-runnable: python3 build_dataset.py
"""
import hashlib, json, math, re, sqlite3
from pathlib import Path

ROOT = Path('/home/hatch/workspace/genesis-os')
HERE = Path(__file__).resolve().parent
import sys as _sys; _sys.path.insert(0, str(HERE.parent))
from frozen_guard import write_heldout  # noqa: E402  (TS-001: frozen held-outs never change silently)
FROZEN_HELDOUT_SHA256 = '23452d59cdcbf897a54bbdb3fbea8d89a449efe6c7d6f543b906fe64e91cd632'  # MANIFEST freeze hash; change only with --refreeze + a version bump
REG = ROOT / 'job-storm-ace' / 'registry.json'
KB = ROOT / 'job-storm-ace' / 'kb' / 'ace_kb.sqlite'
FILTER = ROOT / 'job-storm-ace' / 'ace_filter.json'
DESIGN = ROOT / 'job-storm-ace' / 'DESIGN-ACE.md'
DETECTOR = ROOT / 'job-storm-ace' / 'ace_detector_v2.py'
ANSWERS = ROOT / 'war-room' / 'JOB_STORM_ANSWERS_2026-10-31.md'
COMMAND = ROOT / 'war-room' / 'JOB_STORM_COMMAND_2026-10-31.md'

BANNED = ['630-210-5724', 'brandonduda8@gmail.com', 'hsurr:', 'sk-',
          'BEGIN PRIVATE KEY', 'Bearer ', 'api_key', 'password']
stats = {'dropped_scan': 0}

def clean(rec):
    blob = json.dumps(rec, ensure_ascii=False)
    if any(b in blob for b in BANNED):
        stats['dropped_scan'] += 1
        return None
    return rec

def feats(e):
    parts = [f"employer: {e.get('employer')}", f"role: {e.get('role')}",
             f"lane: {e.get('lane')}", f"pay: {e.get('pay')}",
             f"employer_domain_verified: {e.get('employer_domain_verified')}",
             f"score: {e.get('score')}"]
    return '; '.join(str(p) for p in parts)

def verdict_response(e):
    out = [f"VERDICT: {e.get('state')}"]
    for label, key in (('Reason', 'reason'), ('Parked reason', 'parked_reason'),
                       ('Next step', 'next_step'), ('Evidence', 'evidence')):
        if e.get(key):
            out.append(f"{label}: {e[key]}")
    return '\n'.join(out)

def main():
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / 'corpus').mkdir(exist_ok=True)
    (HERE / 'heldout').mkdir(exist_ok=True)

    entries = json.loads(REG.read_text())['entries']
    entries.sort(key=lambda e: e['id'])

    def vraw(e):
        return {'type': 'verdict',
                'instruction': ("ACE candidate review. Recorded features: "
                                + feats(e) +
                                "\nPer the ACE rulebook, what is the recorded verdict for this candidate, and why?"),
                'response': verdict_response(e),
                'source': 'genesis-os/job-storm-ace/registry.json',
                'detail': f"registry entry {e['id']} (state {e.get('state')}); fields reproduced verbatim, no text authored",
                '_eid': e['id']}

    # Safety scan FIRST (so the freeze below operates on the clean pool only),
    # then FREEZE HELD-OUT (>=20% of clean verdict pairs, hash-selected),
    # then the training split gets only what the freeze did not take.
    clean_pool = []
    for e in entries:
        r = clean(vraw(e))
        if r: clean_pool.append(r)

    def hkey(r):
        return hashlib.sha256(r['_eid'].encode()).hexdigest()
    held = [r for r in clean_pool if int(hkey(r)[:8], 16) % 5 == 0]
    need = math.ceil(0.20 * len(clean_pool))
    if len(held) < need:
        rest = sorted((r for r in clean_pool if r not in held), key=hkey)
        held += rest[:need - len(held)]
    held_ids = {r['_eid'] for r in held}
    train_pool = [r for r in clean_pool if r['_eid'] not in held_ids]

    held_recs, train_verdicts = [], []
    for i, r in enumerate(sorted(held, key=lambda x: x['_eid']), 1):
        r = dict(r); del r['_eid']; r['id'] = f'ACE-HELDOUT-{i:03d}'
        held_recs.append(r)
    for i, r in enumerate(train_pool, 1):
        r = dict(r); del r['_eid']; r['id'] = f'ACE-V-{i:03d}'
        train_verdicts.append(r)

    held_path = HERE / 'heldout' / 'ace-heldout-v1.jsonl'
    held_sha = write_heldout(held_path, '\n'.join(json.dumps(r, ensure_ascii=False) for r in held_recs) + '\n',
                             FROZEN_HELDOUT_SHA256)

    # ---- KB postings not in the registry, with a recorded reason ----
    db = sqlite3.connect(KB); db.row_factory = sqlite3.Row
    reg_ids = {e['id'] for e in entries}
    kb_extra = []
    for row in db.execute("select ace_id, employer_id, role, lane, pay_text, state, reason from postings where reason is not null"):
        if row['ace_id'] in reg_ids or row['ace_id'] in held_ids:
            continue
        emp = db.execute("select name from employers where id=?", (row['employer_id'],)).fetchone()
        r = {'id': f"ACE-KB-{len(kb_extra)+1:03d}", 'type': 'verdict',
             'instruction': ("ACE candidate review. Recorded features: "
                             f"employer: {emp['name'] if emp else row['employer_id']}; role: {row['role']}; lane: {row['lane']}; pay: {row['pay_text']}"
                             "\nPer the ACE rulebook, what is the recorded verdict for this candidate, and why?"),
             'response': f"VERDICT: {row['state']}\nReason: {row['reason']}",
             'source': 'genesis-os/job-storm-ace/kb/ace_kb.sqlite (postings)',
             'detail': f"KB posting {row['ace_id']}, not present in registry.json; reason verbatim"}
        r = clean(r)
        if r: kb_extra.append(r)

    # ---- Rulebook Q&A: reject_patterns + fit_facts (non-contact) + filter ----
    qa = []
    for row in db.execute("select signature, class, description from reject_patterns order by id"):
        r = {'id': f"ACE-QA-{len(qa)+1:03d}", 'type': 'qa',
             'instruction': f"ACE rulebook: what does the reject pattern '{row['signature']}' (class {row['class']}) catch?",
             'response': row['description'],
             'source': 'genesis-os/job-storm-ace/kb/ace_kb.sqlite (reject_patterns)',
             'detail': f"reject_patterns signature {row['signature']}; description verbatim"}
        r = clean(r)
        if r: qa.append(r)
    for row in db.execute("select fact_key, category, fact_value, status from fit_facts where category != 'contact' order by id"):
        r = {'id': f"ACE-QA-{len(qa)+1:03d}", 'type': 'qa',
             'instruction': f"ACE fit facts: what is Brandon's recorded '{row['fact_key']}' ({row['category']})?",
             'response': f"{row['fact_value']} (status: {row['status']})",
             'source': 'genesis-os/job-storm-ace/kb/ace_kb.sqlite (fit_facts)',
             'detail': f"fit_facts {row['fact_key']}; contact-category facts excluded by the PII rule"}
        r = clean(r)
        if r: qa.append(r)
    filt = json.loads(FILTER.read_text())
    for group, pats in (filt.get('banned_patterns') or {}).items():
        r = {'id': f"ACE-QA-{len(qa)+1:03d}", 'type': 'qa',
             'instruction': f"ACE filter: which posting texts does the banned-pattern group '{group}' reject on sight?",
             'response': 'Banned on sight: ' + '; '.join(f'"{p}"' for p in pats),
             'source': 'genesis-os/job-storm-ace/ace_filter.json',
             'detail': f"banned_patterns.{group}; list verbatim"}
        r = clean(r)
        if r: qa.append(r)
    for field, defn in (filt.get('candidate_schema') or {}).items():
        r = {'id': f"ACE-QA-{len(qa)+1:03d}", 'type': 'qa',
             'instruction': f"ACE candidate schema: what does the field '{field}' mean?",
             'response': str(defn),
             'source': 'genesis-os/job-storm-ace/ace_filter.json',
             'detail': f"candidate_schema.{field}; definition verbatim"}
        r = clean(r)
        if r: qa.append(r)
    for row in db.execute("select ace_id, employer, event_type, detail from outcomes order by id"):
        r = {'id': f"ACE-QA-{len(qa)+1:03d}", 'type': 'qa',
             'instruction': f"ACE outcomes ledger: what outcome is recorded for {row['ace_id']} ({row['employer']})?",
             'response': f"event: {row['event_type']}" + (f" — {row['detail']}" if row['detail'] else ''),
             'source': 'genesis-os/job-storm-ace/kb/ace_kb.sqlite (outcomes)',
             'detail': f"outcomes row for {row['ace_id']}; fields verbatim"}
        r = clean(r)
        if r: qa.append(r)

    # ---- Brandon-ruling pairs from JOB_STORM_ANSWERS ----
    rulings = []
    text = ANSWERS.read_text()
    for m in re.finditer(r"✅ \*\*BRANDON RULED[^\n]*\*\*(.*?)(?=\n### |\n## |\Z)", text, re.S):
        body = ' '.join(m.group(1).split())[:1800]
        r = {'id': f"ACE-R-{len(rulings)+1:03d}", 'type': 'qa',
             'instruction': "Job Storm: what is Brandon's ruling of record on this application question?",
             'response': body,
             'source': 'genesis-os/war-room/JOB_STORM_ANSWERS_2026-10-31.md',
             'detail': 'BRANDON RULED block; ruling text verbatim (whitespace-normalized only)'}
        r = clean(r)
        if r: rulings.append(r)
    m = re.search(r"\*\*Integrity rules \(inherited, absolute\):\*\*(.*?)\n", text)
    if m:
        r = {'id': f"ACE-R-{len(rulings)+1:03d}", 'type': 'qa',
             'instruction': "Job Storm: what are the integrity rules for application answers?",
             'response': m.group(1).strip(),
             'source': 'genesis-os/war-room/JOB_STORM_ANSWERS_2026-10-31.md',
             'detail': 'integrity-rules line; verbatim'}
        r = clean(r)
        if r: rulings.append(r)
    for m in re.finditer(r"✅ \*\*ANSWERED [^\n]*", text):
        r = {'id': f"ACE-R-{len(rulings)+1:03d}", 'type': 'qa',
             'instruction': "Job Storm: what is Brandon's answered ruling of record on this open question?",
             'response': ' '.join(m.group(0).split())[:1200],
             'source': 'genesis-os/war-room/JOB_STORM_ANSWERS_2026-10-31.md',
             'detail': 'ANSWERED queue item; text verbatim (whitespace-normalized only)'}
        r = clean(r)
        if r: rulings.append(r)
    # Universal-answers table rows (Brandon's facts of record; the safety
    # scan drops the email/phone rows automatically).
    in_table = False
    for line in text.split('\n'):
        if line.startswith('## 1. UNIVERSAL ANSWERS'):
            in_table = True
            continue
        if in_table and line.startswith('## '):
            break
        if in_table and line.startswith('|') and '---' not in line and 'Question' not in line:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 2 and cells[0] and cells[1]:
                r = {'id': f"ACE-R-{len(rulings)+1:03d}", 'type': 'qa',
                     'instruction': f"Job Storm application answers: {cells[0]}",
                     'response': cells[1][:1200],
                     'source': 'genesis-os/war-room/JOB_STORM_ANSWERS_2026-10-31.md',
                     'detail': 'universal-answers table row; answer verbatim'}
                r = clean(r)
                if r: rulings.append(r)

    # ---- Doc chunks: DESIGN-ACE sections + detector doctrine + floor lines ----
    docs = []
    def add_doc(src_path, src_label, chunk, detail):
        if len(chunk.strip()) < 40:
            return
        r = {'id': f"ACE-D-{len(docs)+1:03d}", 'type': 'doc',
             'text': chunk.strip()[:6000],
             'source': src_label, 'detail': detail}
        r = clean(r)
        if r: docs.append(r)
    dtext = DESIGN.read_text()
    for sec in re.split(r"\n(?=## )", dtext):
        title = sec.split('\n', 1)[0][:80]
        add_doc(DESIGN, 'genesis-os/job-storm-ace/DESIGN-ACE.md', sec,
                f'DESIGN-ACE section "{title}"; verbatim, capped 6000 ch')
    det = DETECTOR.read_text().split('\n')
    add_doc(DETECTOR, 'genesis-os/job-storm-ace/ace_detector_v2.py',
            '\n'.join(det[:100]),
            'detector v2 header + hard-rule block (source excerpt, lines 1-100); the rules AS WRITTEN in code')
    for line in COMMAND.read_text().split('\n'):
        if re.search(r"\$(15|16)|floor", line) and len(line.strip()) > 30:
            add_doc(COMMAND, 'genesis-os/war-room/JOB_STORM_COMMAND_2026-10-31.md',
                    line, 'pay-floor line from the storm command; verbatim')

    # ---- Write corpus ----
    def dump(name, recs):
        p = HERE / 'corpus' / name
        p.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in recs) + ('\n' if recs else ''))
        return len(recs)
    counts = {
        'verdicts_train.jsonl': dump('verdicts_train.jsonl', train_verdicts + kb_extra),
        'rulebook_qa.jsonl': dump('rulebook_qa.jsonl', qa),
        'rulings.jsonl': dump('rulings.jsonl', rulings),
        'docs.jsonl': dump('docs.jsonl', docs),
    }
    merged = train_verdicts + kb_extra + qa + rulings + docs
    counts['ace-v1.jsonl (merged)'] = dump('ace-v1.jsonl', merged)
    total_bytes = sum((HERE / 'corpus' / n).stat().st_size for n in
                      ['verdicts_train.jsonl', 'rulebook_qa.jsonl', 'rulings.jsonl', 'docs.jsonl'])
    print(json.dumps({'counts': counts, 'heldout_records': len(held_recs),
                      'heldout_ids': sorted(held_ids), 'heldout_sha256': held_sha,
                      'registry_entries': len(entries), 'train_verdicts_registry': len(train_verdicts),
                      'kb_extra_verdicts': len(kb_extra), 'dropped_scan': stats['dropped_scan'],
                      'corpus_bytes_per_type_files': total_bytes}, indent=1))

if __name__ == '__main__':
    main()
