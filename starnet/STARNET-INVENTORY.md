# STARNET-INVENTORY (WO-STARNET-MAX-001 §1), part 1: from source

**Status: PARTIAL.** WO §1 asks for an inventory "from the S1's own StarNet tree". That tree is not reachable from any
seat Claude has: S1's last beacon seen by Claude was 2026-10-24. This part inventories what **is** provable today:
**upstream StarNet's source**. Part 2 (the live state of each component on S1) is owed from the S1 sitting (debt
Z-11).

**Source:** `github.com/androoAGI/starnet` main `74fcd504` (2026-10-29), package 0.14.1, MIT code (the name and art
are excluded per its NOTICE). It was read as text in a sparse clone. **No StarNet code was executed**; the session's
permission system refused that, correctly. The facts below come from the files named.

## 1. Brandon's question: "Does StarNet offer any agents? Any special agents?"

**Yes. StarNet is itself an agent harness.** Its README: *"a local-first desktop harness where you create AI agents,
organize them into a crew… Night Shift: leave the station running and agents keep working inside an explicit,
adjustable leash."*

| What | Where in source | Note |
|---|---|---|
| **55 built-in specialist classes** | `shared/specialties.js` (`BUILTINS`), also used by `team.summon` (`sidecar/index.js:492-495`) | Each class has a persona, a model tier, the station gear it draws on, skills, a purpose and a manual. |
| **The lead agent** (the Commander's agent) plus a **crew** | `sidecar/overseer.js`, `sidecar/subagents.js` (durable background workers, resumable, stale-on-restart) | Real concurrent runs, each with its own workspace and permissions |
| **Night Shift**, server-side | `sidecar/nightshift.js` + `nightshift-driver.js` | About one autonomous beat every 45 min while away; leash-capped, E-STOP-aware |
| **Scout** | `sidecar/scout.js` | Drafts new agent prospects and recipes; propose-and-confirm, and "nothing auto-joins the roster" |
| **Cron / routines** | `sidecar/cron*.js`, `routine-*.js` | Scheduled agent runs |
| **MCP client** (stdio + HTTP) and **MCP serve** | `sidecar/mcp/` | Per WO-STARNET-002: serve proxies every tool on the master token, and stdio needs a Docker Safe Cell |
| **24/7 QA loops** (Overseer, Truth Auditor, Green Guardian, Janitor, Adversarial Reviewer…) | `loops/README.md` | These are **StarNet's own development loops**, run in Claude Code on StarNet's repo. They are not product agents. |

**The 55 classes, sorted by how they meet Genesis's fences:**

- **Directly useful as charterable residents** (reversible or read-only by design):
  - Night Shift (`nightwatch`), whose manual says to "PARK anything irreversible (spending, sending, deleting,
    publishing)";
  - Team Lead (`foreman`), Scout, Researcher, Analyst, Engineer, QA Tester (`apptester`), Security Auditor,
    Reviewer, Archivist, Digest Writer (`herald`), Automator (`operator`), Product Manager (`drafter`), DevOps
    Engineer (`deployer`; production deploys stay Level C).
- **Benched under Genesis charters** (they touch money, sends, accounts or logged-in sites, so Level C applies):
  Treasurer, Negotiator, Deal Finder (`broker`), Deal Closer (`closer`), Inbox Manager (`envoy`), Virtual Assistant
  (`pilot`, which signs in and fills forms on real sites), Lead Finder (`prospector`), Support Agent (sends replies).
  - They can run only as **draft-only**: they park the act for Brandon's tap, exactly as Night Shift's own manual
    does.
- **Personal-life classes** (Health Organizer, Home Manager, Trip Planner, Job Hunter, Teacher and so on): outside
  the business program. Not proposed.
- **Name collision:** StarNet's class `anchor` is a *Newsreader*. It is **unrelated** to the fleet's "anchor :8888"
  service. Don't confuse them.

**Mapping to the Platinum roster** (proposal; consolidate, don't duplicate):
- Night Builder ↔ StarNet Night Shift (leash + park-irreversible is already its law);
- Watch Minions ↔ Scout ("watches, and only speaks on a change");
- Scorekeeper ↔ Digest Writer;
- the **flagship** ↔ a lead agent on S1 with Team Lead orchestration.

Each still needs a GHOST charter. StarNet's own leash and consent are a second lock, not a replacement.

## 2. Components named by the WO, against what source and the mirror can prove

| Component | In upstream source? | State on S1 | Genesis marks (identity / MCP / board / owner / proof) |
|---|---|---|---|
| Sidecar / hub **:8787** | yes: `sidecar/index.js` (`PORT` default 8787, loopback) | **UNKNOWN**: no probe | identity only (in the mirror's feed) |
| Display **:8788** | not in the upstream files read; fleet-built | UNKNOWN | identity only |
| Anchor **:8888** | not upstream; a fleet service, **never modified** | UNKNOWN (read-only respect) | identity only |
| Station, vortex, heartbeat timer | "station" = upstream rooms/stations (`docs/station-builder.md`); vortex and heartbeat are not found in the files read | UNKNOWN | identity only |

**Nothing is LIVE-with-proof.** Each row becomes LIVE or BENCHED only from an S1 receipt filed into
`mirror/data/starnet.json`. The StarNet App's StarNet screen reads that file and shows NOT CONNECTED until it exists.

## 3. Known risks carried forward (from source, WO-STARNET-002 §0)

- The default spend cap is $25/day, and **0 means "no cap"**. Genesis's $0 control is *no paid provider keys*,
  never a 0 cap.
- `mcp:serve` exposes every tool on the master token: only behind an allowlisting wrapper.
- The `/v1` ingress has unlimited concurrency when unset; set it to 1.
- The Remote/LAN listener binds the network when Remote is switched on. Keep Remote off; one tailnet listener (the
  hub) per host.
- Some developer-mode tokens are stored in plain text (`PRIVACY.md`). Use a dedicated OS user, and no real
  credentials until the vault review.
