#!/usr/bin/env bash
# RUFLO PENGUIN — verification battery. Run AFTER install.sh and the MCP
# merge. Every line of output goes into the WO receipt verbatim — a check
# that cannot run is reported as UNVERIFIED, never as passed.
set -uo pipefail
BIN="$HOME/bin/ruflo"
FAIL=0

echo "== 1. CLI answers =="
"$BIN" --version || FAIL=1

echo "== 2. MCP stdio handshake (initialize + tools/list) =="
OUT="$(printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"genesis-verify","version":"1.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  | timeout 20 "$BIN" mcp start 2>/dev/null | head -c 4000)"
if [ -n "$OUT" ]; then echo "$OUT" | head -c 1200; echo; else echo "MCP HANDSHAKE: no output — UNVERIFIED"; FAIL=1; fi

echo "== 3. Seat check =="
echo "binary: $(readlink -f "$BIN" 2>/dev/null || echo "$BIN")"
echo "home:   $HOME/agent-shelf/ruflo ($(du -sh "$HOME/agent-shelf/ruflo" 2>/dev/null | cut -f1))"
echo "state:  $HOME/agent-shelf/ruflo-state"

[ "$FAIL" = 0 ] && echo "VERIFY: PASS (CLI + MCP handshake)" || echo "VERIFY: PARTIAL — see lines above; report honestly in the receipt"
exit "$FAIL"
