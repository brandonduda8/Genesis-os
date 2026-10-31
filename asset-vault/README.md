# Genesis Asset Vault (WO-UNIFIED-GAME-BUSINESS-001, Phase 2)

Every production asset is content-addressed, carries its provenance, and can be replayed against its audit log. The
production root is `/home/hatch/agent-shelf/asset-vault/` (a prune-exempt shelf). Before first use, register the
governor exclusion and the backup law on zane-box; that's Zane's step.

Requires Python 3.10 or later and the standard library. `cryptography` is needed only to sign manifests (GHOST key
format).

```bash
python3 asset-vault/vault.py --root ROOT init
python3 asset-vault/import_netforge.py --root ROOT --game path/to/genesis-arena --title emberwatch --actor claude
python3 asset-vault/vault.py --root ROOT report emberwatch
python3 asset-vault/vault.py --root ROOT audit                         # the Phase 2 acceptance replay
python3 asset-vault/vault.py --root ROOT manifest netforge-stock-0.2.0 --key state/keys/vault.key
python3 asset-vault/vault.py --root ROOT rights <sha256> --clean true --evidence "<what was read, where>" --actor zane
```

## Rules the code enforces (tests in `tests/test_vault.py`, 11 tests)

**Promotion**
- A file goes through staging, then promotion. Its hash is re-checked at promotion, so a file swapped while staged is
  refused.
- Objects are named by their SHA-256 and set read-only.

**Provenance and origin**
- `provenance.source` and `licence` are required.
- A `genesis` asset must also name its generator.
- `origin` is `stock` or `genesis` only. **Third-party streams are refused**: Audius and SoundCloud audio is
  ambience, never a vault asset.

**Rights**
- Every asset enters with `rights_clean = false`.
- Flipping it needs written evidence and a licence on the commercial-OK list: CC0-1.0, MIT, Apache-2.0,
  OWNED-BRANDON. A CC-BY-NC asset can never be marked clean.

**Originality**
- A title is **ORIGINAL** only when every player-facing slot is a `genesis` asset that is also rights-clean.
- CC0 stock can be clean, but it is never original.

**Slots**
- Slots accept vault assets only.

**Audit log**
- `audit.log` is hash-chained JSONL, fsynced on every append.
- `audit` reports any of these:
  - an edited line, a deleted line or a sequence gap;
  - a catalog row whose file is missing or whose bytes changed;
  - a catalog row with no promote entry;
  - a file with no catalog row;
  - a slot pointing outside the vault.

**Manifests**
- Pack manifests carry a digest over their entries, and an optional Ed25519 signature.
- `verify_manifest` catches edited entries, unsigned manifests and missing or altered files.

## First holding: the Emberwatch import (run 2026-10-31, in the cloud session)

The game came from `create-netforge@0.2.0`, survivor template (RECEIPT-NETFORGE-001).

| | Count |
|---|---|
| Model slots the game references (`style.lowpoly.*` in `src/game.ts`) | 28 |
| ...bound to vault files, library hash re-verified against the bytes | **24** |
| ...procedural, no file (the gems and the heal cell are generated in code, MIT) | 4 |
| Library audio files stored unbound (the template doesn't declare which it plays) | 18 |
| Assets in the vault | 42 (7.3 MB) |
| Refused for a hash mismatch | 0 |
| **Audit replay** | **ok: 42 assets, 0 problems**; 67 audit entries |
| Rights-clean | 0 of 24 (by rule; the CC0 evidence is in Genesis-core `RECEIPT-NETFORGE-KIT-INSPECTION-001.md`, and the flip is Zane's) |
| Genesis-original | **0 of 24**: every slot is still stock. `report emberwatch` lists the 24 slots left to replace. |

That scratch vault lived in the session. The real import runs on zane-box against the rebuilt game, with the same two
commands.

## Next (Phase 1 dependencies)

The **asset service** (an MCP wrapper over the media-generation lane) writes through `Vault.add(origin="genesis",
provenance={source, generator})`, then `bind_slot`. It must clone the Genesis MCP v2 pattern (127.0.0.1:8770). That
source isn't in any repo this session can reach, so the five fabric services wait on Zane publishing it, or pointing
to its path.
