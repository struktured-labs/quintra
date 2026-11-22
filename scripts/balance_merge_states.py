#!/usr/bin/env python3
"""Merge per-(stage, hero) make_stage_states.py outputs into one directory.

make_stage_states.py writes one manifest per invocation and aborts a whole
invocation on one failing checkpoint, so balance sweeps generate each
(stage, hero) separately and merge the survivors here.
"""
import json
import shutil
import sys
from pathlib import Path

parts, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
merged = None
for d in sorted(p for p in parts.iterdir() if p.is_dir()):
    m = d / "manifest.json"
    if not m.exists():
        continue
    man = json.loads(m.read_text())
    for rec in man["states"]:
        shutil.copy2(d / rec["file"], out / rec["file"])
    if merged is None:
        merged = man
    else:
        if man.get("rom_sha256") != merged.get("rom_sha256"):
            raise SystemExit(f"{m}: ROM hash differs from the other parts")
        merged["states"].extend(man["states"])
if merged is None:
    raise SystemExit(f"no manifests under {parts}")
(out / "manifest.json").write_text(json.dumps(merged, indent=2) + "\n")
print(f"[states] merged {len(merged['states'])} checkpoints into {out}")
