# GENESIS MASTER RUNTIME

**Brandon's order (2026-10-31):** a master work order to completely maximize
and connect everything Genesis is doing — and a master runtime in the
terminal for Zane and all agents. This directory is that runtime.

## What it is

One stdlib-Python entrypoint that reads the fleet's real sources of truth —
the GHOST job queue (`ghost/queue/`), the ACE job-storm registry
(`job-storm-ace/registry.json`), and the agent registry (`agents.json`
beside it) — and renders the whole operation as one board, one plan, and
one verify pass. No database of its own, no daemon, nothing to babysit:
the registries stay the truth; the runtime is the lens.

## Run it (any host — zane-box, penguin, S1)

```bash
cd genesis-os/master-runtime
python3 master_runtime.py status    # the master board, live data
python3 master_runtime.py board     # same, written to state/BOARD.md
python3 master_runtime.py plan      # what's dispatchable next (WIP cap 3)
python3 master_runtime.py verify    # claims vs receipts — the honesty pass
python3 master_runtime.py dispatch GHOST-Q-003   # by-ID envelope → outbox/
```

## The laws it enforces (in code, not in prose)

- **DONE is never printed.** Grades follow Brandon's ladder — IN BRANDON'S
  HANDS / LIVE ON A MACHINE / BUILT / STAGED / BLOCKED. His acceptance is
  the only DONE, and a script never asserts it.
- **Verify before trust.** Executor claims sit UNVERIFIED until a receipt
  file is read back (`verify`). ACE submissions count only with recorded
  confirmation evidence — the board shows the ratio.
- **Mutations by ID only.** `dispatch` matches one exact queue ID; free-text
  matches are refused (the 2026-10-31 registry mutation law).
- **Human relays are never dispatched.** A job whose path is Brandon's
  hands (e.g. GHOST-Q-008, the Claude grade relay) is refused by the
  dispatcher and labeled as his in every plan.
- **Writes stay home.** The runtime writes only `state/` and `outbox/`
  inside its own directory — path containment is asserted on every write.
- **Level C is untouched.** No money moves, nothing publishes, no account
  is created, no signature is applied — by this tool, ever. Envelopes carry
  the fences to the executor verbatim, including the 429 hard-stop.

## Pieces

- `master_runtime.py` — the runtime (stdlib only, Python 3)
- `agents.json` — every agent: role, surface, capabilities, limits.
  Ruflo was seated first-class here 2026-10-31 (penguin home).
- `lanes.json` — sources, lane probes, the WIP-3 workstreams, the parked list
- `ruflo-penguin/` — the Ruflo first-class install pack for penguin
- `state/BOARD.md` — the generated board (regenerate with `board`)
- `outbox/` — dispatch envelopes, store-and-forward: they wait for the
  executor's next contact. Nothing is ever "sent" by the runtime itself.

## Standing truth it surfaces today (2026-10-31)

7 verified job submissions (Integrity's contingent offer SIGNED), the
GHOST queue intact at 10 jobs + this program's additions, Genesis Core and
the NIM proxy answering on this host — and the egress router, LiteLLM, and
OCE doors dark after the last VM recycle, reported as dark doors, never as
dead services.
