#!/usr/bin/env python3
"""Import a Net Forge game's stock assets into the vault and bind them to the title's slots.

  python3 asset-vault/import_netforge.py --root VAULT --game path/to/genesis-arena --title emberwatch --actor claude

* Model slots: every `style.<style>.<id>` the game's src/game.ts references, resolved through the installed
  asset library's own index.json (path + sha256). The library's recorded hash must match the bytes on disk, or the
  asset is refused.
* The audio files the library ships go in as pack stock, unbound: which sounds the template plays isn't declared in
  game.ts, so binding them to slots would be a guess.
* Everything enters origin='stock', rights_clean=FALSE. The licence field records what the library's NOTICE
  says (CC0-1.0); flipping rights_clean is a separate, evidenced `rights` call by a reviewer.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault import Vault, VaultError, sha256_file  # noqa: E402

LIB = ("node_modules", "@netforge", "asset-library-files")


def run(root: str, game: str, title: str, actor: str) -> dict:
    lib = os.path.join(game, *LIB)
    meta = json.load(open(os.path.join(lib, "package.json")))
    index = json.load(open(os.path.join(lib, "library", "index.json")))["assets"]
    src = open(os.path.join(game, "src", "game.ts")).read()
    used = sorted(set(re.findall(r"style\.[a-z0-9]+\.[a-z0-9_]+", src)))
    audio = sorted(k for k in index if k.startswith("audio."))
    v = Vault(root) if os.path.exists(os.path.join(root, "CATALOG.sqlite")) else Vault.init(root, actor)
    pack = f"netforge-stock-{meta['version']}"
    out = {"title": title, "pack": pack, "bound": [], "unbound_audio": [], "refused": [], "missing": []}
    for key in used + audio:
        ent = index.get(key)
        if not ent:
            out["missing"].append(key)
            continue
        path = os.path.join(lib, "library", ent["path"])
        if not os.path.exists(path) or sha256_file(path) != ent["sha256"]:
            out["refused"].append(key)
            continue
        v.add(path, name=key, media_type=mimetypes.guess_type(path)[0] or "model/gltf-binary", pack=pack,
              origin="stock", licence="CC0-1.0",
              provenance={"source": f"npm:{meta['name']}@{meta['version']}/library/{ent['path']}",
                          "library_sha256": ent["sha256"], "notice": "asset-library-files/NOTICE (CC0 1.0 per pack)"},
              actor=actor)
        if key in used:
            v.bind_slot(title, key, ent["sha256"], player_facing=True, actor=actor)
            out["bound"].append(key)
        else:
            out["unbound_audio"].append(key)
    out["report"] = v.title_report(title)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("root", "game", "title", "actor"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args()
    try:
        out = run(a.root, a.game, a.title, a.actor)
    except VaultError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()}, indent=1))
    if out["missing"] or out["refused"]:
        print(json.dumps({"missing": out["missing"], "refused": out["refused"]}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
