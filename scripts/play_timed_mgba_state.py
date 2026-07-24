#!/usr/bin/env python3
"""Open a verified five-minute training checkpoint in mGBA-Qt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=ROOT / "rom/working/quintra.gbc")
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp/timed-mgba-states")
    parser.add_argument("--minutes", type=int, default=30)
    args = parser.parse_args()
    manifest_path = args.state_dir / "manifest.json"
    if not manifest_path.is_file():
        parser.error(f"missing {manifest_path}; run make timed-mgba-states")
    manifest = json.loads(manifest_path.read_text())
    if sha256(args.rom) != manifest["rom_sha256"]:
        parser.error(
            "timed native checkpoints belong to another ROM; "
            "run make timed-mgba-states")
    matches = [
        record for record in manifest["states"]
        if record["minute"] == args.minutes
    ]
    if len(matches) != 1:
        available = ", ".join(
            str(record["minute"]) for record in manifest["states"])
        parser.error(
            f"minute {args.minutes} is unavailable; choose one of {available}")
    record = matches[0]
    state = args.state_dir / record["file"]
    if not state.is_file() or sha256(state) != record["sha256"]:
        parser.error("timed native checkpoint hash does not match its manifest")
    print(f"[play-timed-mgba] {record['minute']}m "
          f"stage={record['stage']} room={record['room_counter']} "
          f"bosses={record['bosses_beaten']} {state.name}", flush=True)
    os.execv(
        "/bin/bash",
        ["bash", str(ROOT / "mgba-qt.sh"), "-t", str(state), str(args.rom)])


if __name__ == "__main__":
    main()
