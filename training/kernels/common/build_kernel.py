#!/usr/bin/env python3
"""Build self-contained Kaggle kernel directories from templates/lora_kernel.py.

  python3 training/kernels/common/build_kernel.py --all          # writes training/kernels/build/<name>/
  python3 training/kernels/common/build_kernel.py --name ghost-lora-v1

Every kernel embeds its corpus and held-out files (gzip + base64) together with their SHA-256 hashes. The held-out
hash is checked HERE against the dataset MANIFEST before anything is written: a mismatch refuses the build.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)
TROOT = os.path.dirname(KROOT)
DATA = os.path.join(TROOT, "datasets")
OWNER = "brandonduda"

LORA = {"lora_r": 16, "lora_alpha": 32, "lora_dropout": 0.05, "lr": 2e-4, "grad_accum": 4, "max_len": 1536}
CANDIDATES = ["Qwen/Qwen2.5-7B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3", "Qwen/Qwen2.5-Coder-7B-Instruct"]
DEFAULT_BASE = "Qwen/Qwen2.5-7B-Instruct"  # placeholder until the line's h2h run picks the winner

KERNELS = {
    "ghost-lora-v1": {"line": "ghost", "mode": "train", "corpus": "ghost-v1/corpus/ghost-v1.jsonl",
                      "heldout": "ghost-v1/heldout/ghost-heldout-v1.jsonl",
                      "heldout_sha256": "74d68f5329388dbc1f9162f6052bb4f4cb3ecd04303bfab1823d428c1a518f2a",
                      "epochs": 4},
    "ace-lora-v1": {"line": "ace", "mode": "train", "corpus": "ace-v1/corpus/ace-v1.jsonl",
                    "heldout": "ace-v1/heldout/ace-heldout-v1.jsonl",
                    "heldout_sha256": "23452d59cdcbf897a54bbdb3fbea8d89a449efe6c7d6f543b906fe64e91cd632",
                    "epochs": 3},
    "ghost-h2h-v1": {"line": "ghost", "mode": "h2h", "corpus": "ghost-v1/corpus/cases_train.jsonl",
                     "heldout": "ghost-v1/heldout/ghost-heldout-v1.jsonl",
                     "heldout_sha256": "74d68f5329388dbc1f9162f6052bb4f4cb3ecd04303bfab1823d428c1a518f2a"},
    "ace-h2h-v1": {"line": "ace", "mode": "h2h", "corpus": "ace-v1/corpus/verdicts_train.jsonl",
                   "heldout": "ace-v1/heldout/ace-heldout-v1.jsonl",
                   "heldout_sha256": "23452d59cdcbf897a54bbdb3fbea8d89a449efe6c7d6f543b906fe64e91cd632"},
}


class BuildRefused(RuntimeError):
    pass


def _embed(path):
    raw = open(path, "rb").read()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "b64gz": base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")}


def scoring_source():
    src = open(os.path.join(HERE, "scoring.py"), encoding="utf-8").read()
    return src.replace("from __future__ import annotations\n", "")  # the template already starts with it


def config_for(name, base=None, dry_max_steps=4):
    k = KERNELS[name]
    corpus_name, held_name = os.path.basename(k["corpus"]), os.path.basename(k["heldout"])
    files = {corpus_name: _embed(os.path.join(DATA, k["corpus"])), held_name: _embed(os.path.join(DATA, k["heldout"]))}
    if files[held_name]["sha256"] != k["heldout_sha256"]:
        raise BuildRefused(f"{name}: held-out {held_name} hash {files[held_name]['sha256']} != manifest "
                           f"{k['heldout_sha256']} — refusing to build a void battery")
    cfg = {"name": name, "line": k["line"], "mode": k["mode"], "seed": 1234, "max_new_tokens": 256,
           "corpus_file": corpus_name, "heldout_file": held_name, "expected_heldout_sha256": k["heldout_sha256"],
           "files": files}
    if k["mode"] == "train":
        cfg["base_model"] = base or DEFAULT_BASE
        cfg["lora"] = dict(LORA, epochs=k["epochs"], dry_max_steps=dry_max_steps)
    else:
        cfg["candidates"] = CANDIDATES
        cfg["h2h_max_items"] = 40
    return cfg


def render(cfg):
    tpl = open(os.path.join(KROOT, "templates", "lora_kernel.py"), encoding="utf-8").read()
    assert tpl.count("__CONFIG_JSON__") == 1 and tpl.count("# __SCORING__") == 1
    return tpl.replace("# __SCORING__", scoring_source()).replace("__CONFIG_JSON__", repr(json.dumps(cfg)))


def build(name, out_root, base=None):
    cfg = config_for(name, base)
    d = os.path.join(out_root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "main.py"), "w", encoding="utf-8") as f:
        f.write(render(cfg))
    meta = {"id": f"{OWNER}/{name}", "title": name, "code_file": "main.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": True, "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
            "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    digest = hashlib.sha256(open(os.path.join(d, "main.py"), "rb").read()).hexdigest()
    return {"kernel": name, "dir": d, "main_sha256": digest, "mode": cfg["mode"],
            "base_model": cfg.get("base_model"), "candidates": cfg.get("candidates"),
            "files": {n: s["sha256"] for n, s in cfg["files"].items()}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", choices=sorted(KERNELS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--base", help="base model for train kernels (the h2h winner)")
    ap.add_argument("--out", default=os.path.join(KROOT, "build"))
    a = ap.parse_args(argv)
    names = sorted(KERNELS) if a.all else [a.name]
    if not names or names == [None]:
        ap.error("--name or --all")
    print(json.dumps([build(n, a.out, a.base) for n in names], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
