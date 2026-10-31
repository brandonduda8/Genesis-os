"""Frozen held-out guard (WO-MASTER-TROUBLESHOOTER-001 incident TS-001, prevention rule).

A held-out set is frozen by its SHA-256 (recorded in the dataset MANIFEST). The builders used to rewrite it on every
run, and they re-pick the split from fleet inputs that change daily, so one routine re-run could silently replace a
frozen battery. This guard refuses any write that would change a frozen file. Changing a frozen set is a version
decision: pass --refreeze AND bump the version, and record the new hash in the MANIFEST.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


class FrozenHeldoutChange(SystemExit):
    pass


def write_heldout(path: Path, text: str, frozen_sha256: str, argv=None) -> str:
    argv = sys.argv if argv is None else argv
    new = text.encode("utf-8")
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == frozen_sha256:
        if new == path.read_bytes():
            return frozen_sha256  # identical: nothing to do, the freeze holds
        if "--refreeze" not in argv:
            raise FrozenHeldoutChange(
                f"REFUSED: {path} is frozen (sha256 {frozen_sha256[:12]}…) and this build would change it. "
                "Frozen held-outs never change silently: re-freezing is a version decision — re-run with "
                "--refreeze, bump the version and record the new hash in the MANIFEST.")
    path.write_bytes(new)
    return hashlib.sha256(new).hexdigest()
