# RECEIPT — GHOST SERVER v2 · P2 Doors + acceptance trio (module 3)

**Grade: BUILT** (lab and cloud). **"Proven against the live egress router": OWED to Zane.** The router's source isn't
on GitHub, and :18955 doesn't exist in this container.

**File:** `ghost-server/ghost/doors.py` · **Config:** `config/doors.json`

## What is built

- **One hard total deadline per request (5 s).** It covers connect, proxy CONNECT, TLS and the response read. This is
  the fix for the "plain connection hung 15 s" case.
- **Door kinds:** `direct`, and `http_proxy` (absolute-URI for http, CONNECT for https), with an optional relay token
  read from a 0600 file at call time and never logged.
- **Circuit breaker:** 3 consecutive failures open it. Cool-down starts at 60 s and doubles up to 15 min. Half-open
  allows one probe. **A 429 opens it for at least 15 min and stops the probe round**, so no further legs are sent.
- **Stats:** a ring of the last 64 results gives p50/p95 latency and error counts by class (timeout, refused, dns,
  tls, proxy_refused, http_4xx, http_5xx, rate_limited, breaker_open).
- **Heal signal = the acceptance trio:** GitHub GET, a NIM completion and a pip fetch, **all through the same door**.
  The verdict is HEALED only when all three pass; one or two passing is PARTIAL.

## Tests (lab: real sockets with a local proxy that can be killed and healed)

`tests/test_doors_codeact.py::Doors` has 6 tests, all OK. They show:

1. All three legs really traverse the proxy, including the POST for the NIM leg.
2. PARTIAL is never reported as healed.
3. A dead door is DARK, and the breaker opens, refuses requests, and goes half-open after the cool-down.
4. **A stall (the proxy accepts and never answers) fails in 4.5–5.5 s**, inside the 5 s bar.
5. 429 is a hard stop: one request, then the breaker opens for at least 900 s.
6. Stats are recorded.

## Real network probe from this cloud container (verbatim, 2026-10-31)

```
$ time python3 ghostd.py doors-probe
{"door": "egress", "verdict": "DARK", "healed": false, "legs": {"github": {"ok": false, "error_class": "refused", "ms": 1}, "nim": {"ok": false, "error_class": "refused", "ms": 0}, "pip": {"ok": false, "error_class": "refused", "ms": 0}}, ..., "breaker": "OPEN"}
{"door": "direct", "verdict": "PARTIAL", "healed": false, "legs": {"github": {"ok": false, "status": 403, "error_class": "http_4xx", "ms": 94}, "nim": {"ok": false, "error_class": "dns", "ms": 1}, "pip": {"ok": true, "status": 200, "error_class": "", "ms": 84}}, ..., "breaker": "CLOSED"}
real 0m0.427s
```

What this shows:
- With no router listening, the egress door is DARK in well under a second.
- On the container's own policed network, the direct door got a live pip 200 but GitHub 403 and a NIM DNS failure, so
  it is **PARTIAL and not healed**. That is the honest verdict.
- These are container facts, not zane-box facts.

## OWED (Zane, after §UP-GHOST step 1 relaunches the router)

- Run `python3 ghostd.py doors-probe` on zane-box and paste the output here.
- If the router is not an HTTP forward proxy (DESIGN §4 assumption), only the `http_proxy` kind changes.
- To make the NIM leg real, set `trio.nim.key_file` to a 0600 file path, or point `trio.nim.url` at the local
  nvidia-proxy :18791.
