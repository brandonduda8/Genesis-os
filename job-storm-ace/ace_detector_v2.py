#!/usr/bin/env python3
"""
ACE DETECTOR v2 — the second-pass gate (built 2026-10-31).

Why this exists: detector v1's credential patterns were defeated by curly
apostrophes and varied phrasing, and a degree-credentialed clinical role
floated to a high raw score in an earlier harvest. v2 normalizes text
(curly quotes, case, punctuation) and scans role/employer/step text for
three hard-rule classes:

  CREDENTIAL  degree / license / clinical-credential requirements beyond
              the candidate's record of credentials (equipment certs such
              as forklift / pallet jack are never flagged)
  DRIVING     driver's-license / driving-role requirements (HARD REJECT
              under the candidate's rules)
  RESIDENCY   remote roles restricted to states that exclude the
              candidate's home state; full detection needs the posting
              body (verify stage); the title-level scan catches explicit
              "in <state>" phrasing only, and says so.

The candidate's personal facts (education, credentials, home state,
transport) are NOT kept in this repo. They live in the gitignored local
profile `job-storm-ace/profile.local.json` (see profile.example.json);
this detector's rules do not need them to run.

DRY-RUN BY DEFAULT: prints candidate IDs + matched patterns + recommended
action. It mutates NOTHING. Flips happen by explicit ID under the mutation
law (enumerated write set, read back in the same run) — see --apply with a
reviewed ID list in the calling session, never from this report alone.
"""

import json
import re
import sys
import unicodedata

REG = "registry.json"

CREDENTIAL = [
    r"\bbsw\b", r"\bmsw\b", r"\bbachelor'?s?\b", r"\bmaster'?s degree\b",
    r"\bdegree required\b", r"\bclinician\b", r"\btherapist\b",
    r"\bcounselor\b", r"\bsocial worker\b", r"\brn\b", r"\blpn\b",
    r"\bregistered nurse\b", r"\blicensed (?!.*driver)", r"\blicensure\b",
    r"\bphlebotom", r"\bparamedic\b", r"\bemergency medical\b",
]
DRIVING = [
    r"\bdriver'?s license\b", r"\bcdl\b", r"\bdelivery driver\b",
    r"\broute driver\b", r"\bdriver\b", r"\bdriving\b", r"\bcourier\b",
]
RESIDENCY = [
    r"\bmust reside in\b", r"\bbased in (az|fl|ga|nv|ny|nc|tn|tx|ut|va)\b",
    r"\b(az|fl|ga|nv|ny|nc|tn|tx|ut|va) residents? only\b",
]
# roles where "driver" is the equipment, not a road vehicle — never flag
DRIVING_EXEMPT = [r"forklift", r"reach truck", r"pallet jack", r"order picker",
                  r"cherry picker", r"stand[- ]up"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return s.lower()


def scan(text):
    t = norm(text)
    hits = []
    if not any(re.search(p, t) for p in DRIVING_EXEMPT):
        for p in DRIVING:
            if re.search(p, t):
                hits.append(("DRIVING", p))
                break
    for p in CREDENTIAL:
        if re.search(p, t):
            hits.append(("CREDENTIAL", p))
            break
    for p in RESIDENCY:
        if re.search(p, t):
            hits.append(("RESIDENCY", p))
            break
    return hits


def main():
    reg = json.load(open(REG))
    states = ("SCORED", "STAGED")
    print(f"# ACE DETECTOR v2 — dry-run over {states} (mutates nothing)")
    flagged = 0
    for e in reg["entries"]:
        if e["state"] not in states:
            continue
        text = " | ".join(str(e.get(k, "")) for k in
                          ("role", "employer", "next_step", "reason"))
        hits = scan(text)
        if hits:
            flagged += 1
            kinds = ", ".join(f"{k}({p})" for k, p in hits)
            action = ("RECOMMEND REJECT — hard rule"
                      if any(k in ("DRIVING", "CREDENTIAL") for k, _ in hits)
                      else "RECOMMEND VERIFY-FIRST")
            print(f"- {e['id']} [{e['state']}] {e.get('role','')} @ "
                  f"{e.get('employer','')} :: {kinds} :: {action}")
    print(f"# flagged {flagged} of "
          f"{sum(1 for e in reg['entries'] if e['state'] in states)} scanned")


if __name__ == "__main__":
    sys.exit(main())
