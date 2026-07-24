#!/usr/bin/env python3
"""Open a manifest-verified native Quintra checkpoint in mGBA-Qt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=ROOT / "rom/working/quintra.gbc")
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp/mgba-states")
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--checkpoint",
                        choices=("entry", "court", "sanctuary", "boss",
                                 "riftwild", "village"),
                        default="entry")
    parser.add_argument("--difficulty", choices=("normal", "easy"), default="easy")
    parser.add_argument("--champion", choices=CHAMPIONS, default="wolfkin")
    args = parser.parse_args()
    manifest_path = args.state_dir / "manifest.json"
    if not manifest_path.is_file():
        parser.error(f"missing {manifest_path}; run make mgba-states")
    manifest = json.loads(manifest_path.read_text())
    if sha256(args.rom) != manifest["rom_sha256"]:
        parser.error("native checkpoints belong to a different ROM; run make mgba-states")
    matches = [
        record for record in manifest["states"]
        if record["checkpoint"] == args.checkpoint
        and record["difficulty"] == args.difficulty
        and record["champion"] == args.champion
        and ((record["after_stage"] == args.stage)
             if args.checkpoint in ("riftwild", "village")
             else (record["stage"] == args.stage))
    ]
    if len(matches) != 1:
        parser.error("requested checkpoint is not present in the native curriculum")
    state = args.state_dir / matches[0]["file"]
    if not state.is_file() or sha256(state) != matches[0]["sha256"]:
        parser.error("native checkpoint hash does not match its manifest")
    print(f"[play-mgba-state] {state.name}", flush=True)
    os.execv(
        "/bin/bash",
        ["bash", str(ROOT / "mgba-qt.sh"), "-t", str(state), str(args.rom)])


if __name__ == "__main__":
    main()
