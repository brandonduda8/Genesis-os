#!/usr/bin/env bash
# RUFLO ON PENGUIN — first-class install (Brandon's order, 2026-10-31)
# Run ON PENGUIN (Crostini), as brandonduda8, from any directory.
# Idempotent: re-running repairs the install in place.
#
# First-class means ALL of these when this script + the WO steps finish:
#   1. `ruflo` CLI on PATH (shim in ~/bin), pinned version, prune-proof home
#   2. Ruflo registered as an MCP server in OpenCode's config on penguin
#   3. A smoke swarm run with its output saved as a receipt
#   4. Ruflo present in the Genesis master runtime agent registry (done
#      fleet-side 2026-10-31 — agents.json, id "ruflo")
#
# Fences: $0 (npm package is free), no accounts, no sudo, no global install,
# nothing outside $HOME. Penguin has direct internet — no proxy games here.
set -euo pipefail

PINNED="3.42.5"                       # the fleet-verified version
HOME_DIR="$HOME/agent-shelf/ruflo"    # prune-proof convention (agent shelf)
STATE_DIR="$HOME/agent-shelf/ruflo-state"
BIN_DIR="$HOME/bin"

echo "== ruflo penguin install =="
command -v node >/dev/null || { echo "FAIL: node not found on penguin — install Node LTS first (WO step 0)"; exit 1; }
command -v npm  >/dev/null || { echo "FAIL: npm not found on penguin"; exit 1; }
node --version; npm --version

mkdir -p "$HOME_DIR" "$STATE_DIR" "$BIN_DIR"

# --- install (pinned; drift is recorded, never silent) --------------------
if [ ! -x "$HOME_DIR/node_modules/.bin/ruflo" ]; then
  if ! npm install --prefix "$HOME_DIR" "ruflo@$PINNED" --no-fund --no-audit; then
    echo "WARN: pinned ruflo@$PINNED unavailable — installing latest 3.x and RECORDING the drift"
    npm install --prefix "$HOME_DIR" "ruflo@3" --no-fund --no-audit
  fi
fi

# --- shim on PATH ----------------------------------------------------------
cat > "$BIN_DIR/ruflo" <<EOF
#!/usr/bin/env bash
# Genesis shim — ruflo's home is the prune-proof agent shelf.
exec node "$HOME_DIR/node_modules/ruflo/bin/ruflo.js" "\$@"
EOF
chmod +x "$BIN_DIR/ruflo"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "NOTE: add $BIN_DIR to PATH in ~/.bashrc";; esac

ACTUAL="$("$BIN_DIR/ruflo" --version 2>/dev/null | head -1 || echo UNKNOWN)"
echo "ruflo version: $ACTUAL (pinned target: $PINNED)"
echo "$ACTUAL" > "$STATE_DIR/VERSION"
echo "INSTALL OK — next: merge opencode-mcp-snippet.json into OpenCode's config, then run verify.sh"
