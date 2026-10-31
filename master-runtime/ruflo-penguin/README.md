# RUFLO ON PENGUIN — the first-class pack

**Brandon's order (2026-10-31):** "put ruflo in the penguin as a first class
agent and tool."

Ruflo is the fleet's swarm conductor (Alliance member since 2026-10-02). Its
zane-box install tree was pruned by the storage governor on 2026-10-21 (the
F6 incident — same sweep that ate OCE/Aider/OpenHands) and the CLI has been
MODULE_NOT_FOUND since. Swarms have run without their conductor ever since.

## Why penguin is the right home

- Penguin is the fleet's build farm: Docker-capable, direct internet (no
  egress-proxy games), and it is where Cody/OpenCode already works.
- MCP clients live there (OpenCode first), so the conductor sits next to its
  first customer.
- The zane-box seat returns separately with the F6 shelf reinstall
  (GHOST-Q-002) — two seats, one registry entry, no split-brain claims:
  penguin is the PRIMARY seat from this order forward.

## What "first-class" means, checkably

1. `ruflo` answers on penguin's PATH, installed pinned (`ruflo@3.42.5`, the
   fleet-verified version) into the prune-proof agent shelf
   (`~/agent-shelf/ruflo`) — never a global/sudo install.
2. Ruflo is registered as an MCP server in OpenCode's config on penguin and
   the handshake verifies (verify.sh §2).
3. Ruflo is in the Genesis master runtime's agent registry with capabilities
   and limits (done fleet-side 2026-10-31: `master-runtime/agents.json`,
   id `ruflo`).
4. One real swarm task runs under a filed WO and lands a receipt — a
   conductor that has never conducted is STAGED, not first-class.

## Files

- `install.sh` — idempotent installer (run on penguin as brandonduda8)
- `opencode-mcp-snippet.json` — the MCP registration entry for OpenCode
- `verify.sh` — CLI + MCP handshake battery; output goes into the receipt

## Fences

$0, no accounts, no sudo, nothing outside `$HOME` on penguin. Ruflo works
only from a filed WO or a Zane dispatch envelope; every worker it spawns
inherits the same fences — spawning never widens authority. Level C remains
Brandon's tap, swarm or no swarm.
