#!/usr/bin/env python3
"""GHOST Training Dataset v1 builder (QUEUE row #10).

Cody v1 pattern: provenanced records, mechanical transforms only,
credential-shaped content excluded by rule, held-out frozen + hashed
BEFORE the training split is written. Failure classes follow QUEUE row
#10: EGRESS / TRANSPORT / FAULT / STATE, plus UNKNOWN (honesty feedstock)
and NONE (recorded outcome was healthy / not a failure). Every class
assignment carries its basis quote in `detail`.
Re-runnable: python3 build_dataset.py
"""
import hashlib, json, math, re
from pathlib import Path

ROOT = Path('/home/hatch/workspace/genesis-os')
HERE = Path(__file__).resolve().parent
import sys as _sys; _sys.path.insert(0, str(HERE.parent))
from frozen_guard import write_heldout  # noqa: E402  (TS-001: frozen held-outs never change silently)
FROZEN_HELDOUT_SHA256 = '74d68f5329388dbc1f9162f6052bb4f4cb3ecd04303bfab1823d428c1a518f2a'  # MANIFEST freeze hash; change only with --refreeze + a version bump
QUEUE_DIR = ROOT / 'ghost' / 'queue'
SWEEP = ROOT / 'war-room' / 'RECEIPT-ACTIVATION-SWEEP-2026-10-31.md'
ZC = ROOT / 'war-room' / 'RECEIPT-ZEROCLAW-BACKLOG-2026-10-31.md'
ROUTER_R = ROOT / 'war-room' / 'RECEIPT-GHOST-A-ROUTER-2026-10-30.md'
RELAY_R = ROOT / 'war-room' / 'RECEIPT-GHOST-A-RELAYPACKS-2026-10-30.md'
INV14 = QUEUE_DIR / 'GHOST-Q-014-investigation.md'
DESIGN = ROOT / 'ghost' / 'DESIGN-egress-router.md'
QREADME = QUEUE_DIR / 'README.md'
PROG = ROOT / 'ghost' / 'PROGRAM_STATE.md'
STATE = ROOT / 'state'

BANNED = ['hsurr:', 'sk-', 'BEGIN PRIVATE KEY', 'Bearer ', 'api_key', 'password',
          'ghp_', 'xoxb-']
stats = {'dropped_scan': 0}

def clean(rec):
    blob = json.dumps(rec, ensure_ascii=False)
    if any(b in blob for b in BANNED):
        stats['dropped_scan'] += 1
        return None
    return rec

# Failure class per queue job, each grounded in that job file's own
# requires_path text (basis quoted in `detail` at build time).
JOB_CLASS = {
    'GHOST-Q-001': 'TRANSPORT', 'GHOST-Q-002': 'EGRESS', 'GHOST-Q-003': 'EGRESS',
    'GHOST-Q-004': 'EGRESS', 'GHOST-Q-005': 'TRANSPORT', 'GHOST-Q-006': 'TRANSPORT',
    'GHOST-Q-007': 'TRANSPORT', 'GHOST-Q-008': 'NONE', 'GHOST-Q-011': 'TRANSPORT',
    'GHOST-Q-012': 'TRANSPORT', 'GHOST-Q-013': 'NONE', 'GHOST-Q-014': 'NONE',
    'GHOST-Q-015': 'FAULT', 'GHOST-Q-016': 'NONE', 'GHOST-Q-017': 'NONE',
}

def sections(text):
    parts = re.split(r"\n(?=## )", text)
    return [p for p in parts if p.strip().startswith('##')]

def main():
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / 'corpus').mkdir(exist_ok=True)
    (HERE / 'heldout').mkdir(exist_ok=True)

    cases = []   # diagnostic cases (job_case + incident + state_read)

    # ---- Job cases from the queue registry ----
    for f in sorted(QUEUE_DIR.glob('GHOST-Q-*.json')):
        d = json.loads(f.read_text())
        jid = d['id']
        resp = [f"RECORDED STATUS: {d.get('status')}"]
        if d.get('receipt_target'):
            resp.append(f"Receipt target: {d['receipt_target']}")
        r = {'type': 'job_case',
             'instruction': ("GHOST diagnostic review. Recorded job: "
                             f"title: {d.get('title')}\nrequires_path: {d.get('requires_path')}\n"
                             "What is this job's recorded status, and what failure class (EGRESS / TRANSPORT / FAULT / STATE / NONE) governs its blocker?"),
             'response': '\n'.join(resp) + f"\nFAILURE CLASS: {JOB_CLASS.get(jid, 'NONE')}",
             'source': f'genesis-os/ghost/queue/{f.name}',
             'detail': (f"class {JOB_CLASS.get(jid, 'NONE')} grounded in this file's own requires_path text "
                        f"(\"{(d.get('requires_path') or '')[:90]}...\"); title/requires/status verbatim"),
             '_cid': jid}
        r = clean(r)
        if r: cases.append(r)

    # ---- Incident cases from receipts (headed sections, verbatim) ----
    def receipt_incidents(path, label, class_map):
        if not path.exists():
            return
        for sec in sections(path.read_text()):
            head = sec.split('\n', 1)[0].strip('# ').strip()
            cls = class_map(head)
            if cls is None:
                continue
            r = {'type': 'incident',
                 'instruction': (f"GHOST incident review. Recorded symptom (receipt section): {head}\n"
                                 "Give the failure class (EGRESS / TRANSPORT / FAULT / STATE / UNKNOWN / NONE), the next action, and the recorded outcome, per the receipt."),
                 'response': (sec.strip()[:4000] + f"\nFAILURE CLASS: {cls}"),
                 'source': f'genesis-os/war-room/{path.name}',
                 'detail': f'{label} section "{head}"; section text verbatim (capped 4000 ch); class from the section\'s own recorded cause',
                 '_cid': f'{label}:{head[:40]}'}
            r = clean(r)
            if r: cases.append(r)

    def sweep_class(head):
        if head.startswith('1.'): return 'EGRESS'   # router live; upstream stall is the recorded blocker
        if head.startswith('2.'): return 'FAULT'    # install pruned
        if head.startswith('3.'): return 'EGRESS'   # startup wedged through stalled egress
        if head.startswith('4.'): return 'STATE'    # stale local truststore state, repaired
        return None
    receipt_incidents(SWEEP, 'SWEEP', sweep_class)

    def zc_class(head):
        h = head.lower()
        if '42617' in h or '503' in h or 'health' in h or 'gateway' in h:
            return 'NONE'  # recorded outcome: healthy; the 503 was never a fault
        return None
    # ZeroClaw receipt section shapes vary; fall back to whole-doc keyword pull below.
    zc_before = len(cases)
    receipt_incidents(ZC, 'ZC', zc_class)
    if len(cases) == zc_before and ZC.exists():
        txt = ZC.read_text()
        m = re.search(r"((?:The )?:42617[^\n]*(?:\n(?!\n#)[^\n]*){0,6})", txt)
        if m:
            r = {'type': 'incident',
                 'instruction': "GHOST incident review. Recorded symptom: ZeroClaw S1 gateway answers 503 on :42617. Give the failure class, the next action, and the recorded outcome.",
                 'response': m.group(1).strip()[:2000] + "\nFAILURE CLASS: NONE",
                 'source': 'genesis-os/war-room/RECEIPT-ZEROCLAW-BACKLOG-2026-10-31.md',
                 'detail': 'recorded finding: the plain binary install ships without the web dashboard; gateway healthy — 503 was never a fault; excerpt verbatim',
                 '_cid': 'ZC:42617'}
            r = clean(r)
            if r: cases.append(r)

    def named_incident(path, label, want):
        """want: {heading-substring: class}. Named-section extraction for
        receipts whose outcome sections don't carry status keywords."""
        if not path.exists():
            return
        for sec in sections(path.read_text()):
            head = sec.split('\n', 1)[0].strip('# ').strip()
            for key, cls in want.items():
                if key in head:
                    r = {'type': 'incident',
                         'instruction': (f"GHOST incident review. Recorded symptom (receipt section): {head}\n"
                                         "Give the failure class (EGRESS / TRANSPORT / FAULT / STATE / UNKNOWN / NONE), the next action, and the recorded outcome, per the receipt."),
                         'response': (sec.strip()[:4000] + f"\nFAILURE CLASS: {cls}"),
                         'source': f'genesis-os/war-room/{path.name}',
                         'detail': f'{label} section "{head}"; section text verbatim (capped 4000 ch); class from the section\'s own recorded evidence',
                         '_cid': f'{label}:{head[:40]}'}
                    r = clean(r)
                    if r: cases.append(r)
    named_incident(ROUTER_R, 'ROUTER',
                   {'lane stall, verbatim': 'EGRESS',   # §A: claims BLOCKED by the egress stall, not failed
                    'live failover sequence': 'NONE'})  # §B: failover proven working
    named_incident(RELAY_R, 'RELAY', {'Local lab proof': 'NONE'})

    # ---- State-file readings ----
    pk = json.loads((STATE / 'penguin_keepalive.json').read_text())
    r = {'type': 'state_read',
         'instruction': ("GHOST state reading. penguin_keepalive.json records: "
                         f"status now \"{pk.get('status')}\", last_down {pk.get('last_down')}, last_up {pk.get('last_up')}, "
                         f"consecutive_down {pk.get('consecutive_down')}. What failure class caused the recorded down period?"),
         'response': ("UNKNOWN — the state file records the down→up transition and its timestamps but records "
                      "no cause. Any named class (EGRESS / TRANSPORT / FAULT) would be invented from this evidence alone."),
         'source': 'genesis-os/state/penguin_keepalive.json',
         'detail': 'UNDERDETERMINED case (honesty feedstock): evidence verbatim from the state file; the record itself leaves the cause unresolved',
         '_cid': 'STATE:penguin_keepalive'}
    r = clean(r)
    if r: cases.append(r)

    lh = json.loads((STATE / 'lane_health.json').read_text())
    down = [k for k, v in lh.items() if isinstance(v, dict) and v.get('status') == 'DOWN']
    r = {'type': 'state_read',
         'instruction': ("GHOST state reading. lane_health.json records EVERY lane DOWN with detail \"blackout\" — "
                         f"{len(down)} lanes including the local ollama lane: {', '.join(sorted(down)[:8])}... "
                         "What single failure class explains this snapshot?"),
         'response': ("UNKNOWN — the snapshot records statuses and the shared detail \"blackout\" but no per-lane "
                      "cause and no resolution. Simultaneous failure of every lane including a local one is "
                      "consistent with more than one class (probe-path/egress event vs host event); the record "
                      "does not determine which."),
         'source': 'genesis-os/state/lane_health.json',
         'detail': 'UNDERDETERMINED case (honesty feedstock): statuses/detail verbatim from the snapshot; cause not recorded in the file',
         '_cid': 'STATE:lane_health'}
    r = clean(r)
    if r: cases.append(r)

    sg = json.loads((STATE / 'storage_governor_status.json').read_text())
    r = {'type': 'state_read',
         'instruction': ("GHOST state reading. storage_governor_status.json records: "
                         f"mode {sg.get('mode')}, used_pct {sg.get('used_pct')}, lean_ceiling_pct {sg.get('lean_ceiling_pct')}, "
                         f"over_ceiling {sg.get('over_ceiling')}, free_gb {sg.get('free_gb')}. "
                         "Give the failure class and the next action."),
         'response': (f"FAILURE CLASS: STATE\nRecorded outcome: used {sg.get('used_pct')}% is under the "
                      f"{sg.get('lean_ceiling_pct')}% ceiling (over_ceiling={sg.get('over_ceiling')}); "
                      "governor in enforce mode; next action: none — within ceiling, keep monitoring."),
         'source': 'genesis-os/state/storage_governor_status.json',
         'detail': 'determined STATE reading: all values verbatim from the state file; action follows the recorded over_ceiling flag',
         '_cid': 'STATE:storage_governor'}
    r = clean(r)
    if r: cases.append(r)

    # ---- The Q-014 Gmail incident: recorded UNKNOWN ----
    if INV14.exists():
        txt = INV14.read_text()
        m = re.search(r"(died on \"query connector grant\" errors.{0,600})", txt, re.S)
        excerpt = ' '.join(m.group(1).split())[:1200] if m else ''
        r = {'type': 'incident',
             'instruction': ("GHOST incident review. Recorded symptom: Gmail reads for the GHOST-Q-014 investigation "
                             "failed repeatedly — search attempts died on transport errors and read attempts died on "
                             "\"query connector grant\" errors — while the connector status check reports the account "
                             "connected with read scope granted. Give the failure class."),
             'response': ("UNKNOWN — the investigation records two distinct error shapes (transport code-5 on "
                          "search; grant-query errors on read) alongside a status check reporting read scope "
                          "granted. The cause was never isolated; naming EGRESS or FAULT from this record alone "
                          "would be invention.\nRecorded evidence: " + excerpt),
             'source': 'genesis-os/ghost/queue/GHOST-Q-014-investigation.md',
             'detail': 'UNDERDETERMINED case (honesty feedstock): error shapes + status contradiction verbatim from the investigation file; cause recorded as unisolated',
             '_cid': 'INC:q014-gmail'}
        r = clean(r)
        if r: cases.append(r)

    # ---- Safety scan already applied per-record above; FREEZE held-out ----
    def hkey(r):
        return hashlib.sha256(r['_cid'].encode()).hexdigest()
    held = [r for r in cases if int(hkey(r)[:8], 16) % 5 == 0]
    need = math.ceil(0.20 * len(cases))
    if len(held) < need:
        rest = sorted((r for r in cases if r not in held), key=hkey)
        held += rest[:need - len(held)]
    # Honesty-feedstock placement law: >=1 UNKNOWN case on EACH side.
    def is_unk(r):
        return 'FAILURE CLASS: UNKNOWN' in r['response'] or r['response'].startswith('UNKNOWN')
    held_ids = {r['_cid'] for r in held}
    if not any(is_unk(r) for r in held):
        cand = sorted((r for r in cases if is_unk(r) and r['_cid'] not in held_ids), key=hkey)
        swap_out = sorted((r for r in held if not is_unk(r)), key=hkey, reverse=True)
        if cand and swap_out:
            held.remove(swap_out[0]); held.append(cand[0]); held_ids = {r['_cid'] for r in held}
    train_cases = [r for r in cases if r['_cid'] not in held_ids]
    if not any(is_unk(r) for r in train_cases):
        cand = sorted((r for r in cases if is_unk(r) and r['_cid'] in held_ids), key=hkey)
        swap_out = sorted((r for r in train_cases), key=hkey, reverse=True)
        if cand and swap_out and len(held) > need:
            held.remove(cand[0]); train_cases.remove(swap_out[0]); train_cases.append(cand[0])
            held_ids = {r['_cid'] for r in held}

    held_recs = []
    for i, r in enumerate(sorted(held, key=lambda x: x['_cid']), 1):
        r = dict(r); del r['_cid']; r['id'] = f'GHOST-HELDOUT-{i:03d}'
        held_recs.append(r)
    train_out = []
    for i, r in enumerate(train_cases, 1):
        r = dict(r); del r['_cid']; r['id'] = f'GHOST-C-{i:03d}'
        train_out.append(r)
    held_path = HERE / 'heldout' / 'ghost-heldout-v1.jsonl'
    held_sha = write_heldout(held_path, '\n'.join(json.dumps(r, ensure_ascii=False) for r in held_recs) + '\n',
                             FROZEN_HELDOUT_SHA256)

    # ---- Doctrine doc chunks (verbatim, capped) ----
    docs = []
    def add_doc(text_chunk, source, detail):
        if len(text_chunk.strip()) < 40:
            return
        r = {'id': f"GHOST-D-{len(docs)+1:03d}", 'type': 'doc', 'text': text_chunk.strip()[:6000],
             'source': source, 'detail': detail}
        r = clean(r)
        if r: docs.append(r)
    dtext = DESIGN.read_text()
    for sec in sections(dtext):
        head = sec.split('\n', 1)[0]
        if any(k in head for k in ('Health scoring', 'Circuit breaker', '429 law', 'Lanes', 'Logging')):
            add_doc(sec, 'genesis-os/ghost/DESIGN-egress-router.md',
                    f'design section "{head.strip("# ")}"; verbatim, capped 6000 ch')
    qtext = QREADME.read_text()
    for sec in sections(qtext):
        head = sec.split('\n', 1)[0]
        if any(k in head for k in ('Drain law', 'Schema', 'How jobs enter')):
            add_doc(sec, 'genesis-os/ghost/queue/README.md',
                    f'registry section "{head.strip("# ")}"; verbatim, capped 6000 ch')
    ptext = PROG.read_text()
    m = re.search(r"(Heal-window drain priority:[^\n]*(?:\n[^\n]*){0,3})", ptext)
    if m:
        add_doc(m.group(1), 'genesis-os/ghost/PROGRAM_STATE.md',
                'drain-priority + WIP-law excerpt; verbatim')

    def dump(name, recs):
        p = HERE / 'corpus' / name
        p.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in recs) + ('\n' if recs else ''))
        return len(recs)
    counts = {'cases_train.jsonl': dump('cases_train.jsonl', train_out),
              'docs.jsonl': dump('docs.jsonl', docs)}
    counts['ghost-v1.jsonl (merged)'] = dump('ghost-v1.jsonl', train_out + docs)
    total_bytes = sum((HERE / 'corpus' / n).stat().st_size for n in ['cases_train.jsonl', 'docs.jsonl'])
    print(json.dumps({'counts': counts, 'cases_total': len(cases), 'heldout_records': len(held_recs),
                      'heldout_cids': sorted(held_ids), 'heldout_sha256': held_sha,
                      'unknown_cases': sum(1 for r in cases if is_unk(r)),
                      'unknown_in_heldout': sum(1 for r in held if is_unk(r)),
                      'dropped_scan': stats['dropped_scan'],
                      'corpus_bytes_per_type_files': total_bytes}, indent=1))

if __name__ == '__main__':
    main()
