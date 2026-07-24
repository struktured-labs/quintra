#!/usr/bin/env python3
"""Generate verified native mGBA snapshots every five minutes of real play."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from make_mgba_states import sha256, symbols, verify_cli_state


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
DEFAULT_OUT = ROOT / "tmp/timed-mgba-states"
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def parse_report(path: Path, out: Path) -> list[dict]:
    records = []
    done = False
    for line in path.read_text().splitlines():
        if line == "DONE":
            done = True
            continue
        fields = line.split("\t")
        if len(fields) != 12:
            raise RuntimeError(f"malformed native checkpoint report: {line!r}")
        (filename, scheduled, elapsed, room, bosses, hp, world, world_screen,
         screen, difficulty, class_id, run_seconds) = fields
        state = out / filename
        if not state.is_file() or state.stat().st_size < 1024:
            raise RuntimeError(f"native checkpoint is missing/truncated: {state}")
        bosses_beaten = int(bosses)
        records.append({
            "file": filename,
            "checkpoint": "timed",
            "scheduled_frames": int(scheduled),
            "elapsed_frames": int(elapsed),
            "minute": int(scheduled) // 3600,
            "stage": min(9, bosses_beaten + 1),
            "bosses_beaten": bosses_beaten,
            "room_counter": int(room),
            "hp": int(hp),
            "world_mode": int(world),
            "world_screen": int(world_screen),
            "screen": int(screen),
            "difficulty": "easy" if int(difficulty) else "normal",
            "class_id": int(class_id),
            "champion": CHAMPIONS[int(class_id)],
            "run_seconds": int(run_seconds),
            "bytes": state.stat().st_size,
            "sha256": sha256(state),
        })
    if not done:
        raise RuntimeError("native checkpoint controller did not finish its report")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--mgba", default=os.environ.get(
        "QUINTRA_MGBA_BIN", "mgba-headless"))
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--checkpoint-minutes", type=int, default=5)
    parser.add_argument("--champion", choices=CHAMPIONS, default="picsean")
    parser.add_argument("--difficulty", choices=("normal", "easy"),
                        default="easy")
    parser.add_argument("--run", type=int, default=4)
    parser.add_argument("--target-frame", type=int, default=1000)
    args = parser.parse_args()
    if args.minutes < 1 or args.checkpoint_minutes < 1:
        parser.error("minute durations must be positive")
    if args.minutes % args.checkpoint_minutes:
        parser.error("--minutes must be divisible by --checkpoint-minutes")

    args.rom = args.rom.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    for stale in args.out.glob("quintra-training-*.ss0"):
        stale.unlink()
    report = args.out / ".states.tsv"
    report.unlink(missing_ok=True)
    manifest_path = args.out / "manifest.json"
    manifest_path.unlink(missing_ok=True)

    total_frames = args.minutes * 3600
    interval_frames = args.checkpoint_minutes * 3600
    class_id = CHAMPIONS.index(args.champion)
    with tempfile.TemporaryDirectory(prefix="quintra-timed-mgba.") as temp:
        temp_path = Path(temp)
        env = os.environ.copy()
        env.update({
            "QUINTRA_BALANCE_RUNS": str(args.run),
            "QUINTRA_BALANCE_CLASSES": str(class_id),
            # Allow ten seconds after the final due beat to reach a stable
            # generated room if minute thirty lands inside a slide.
            "QUINTRA_BALANCE_FRAMES": str(total_frames + 600),
            "QUINTRA_BALANCE_HOST_TIMEOUT": "360",
            "QUINTRA_BALANCE_TARGET_FRAME": str(args.target_frame),
            "QUINTRA_BALANCE_OUT": str(temp_path / "balance.csv"),
            "QUINTRA_BALANCE_TRIAL_DIR": str(temp_path / "trials"),
            "QUINTRA_BALANCE_SKIP_REPORT": "1",
            "QUINTRA_MGBA_SAVE_DIR": str(temp_path / "save"),
            "QUINTRA_MGBA_BIN": args.mgba,
            "QUINTRA_BOT_EASY": "1" if args.difficulty == "easy" else "0",
            "QUINTRA_BOT_THREAT_POLICY": "collision",
            "QUINTRA_BOT_STATE_DIR": str(args.out),
            "QUINTRA_BOT_STATE_REPORT": str(report),
            "QUINTRA_BOT_STATE_INTERVAL": str(interval_frames),
        })
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/run_balance_bot.sh"), str(args.rom)],
            cwd=ROOT, env=env, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(
                "controller-driven mGBA checkpoint run failed:\n"
                + result.stdout + result.stderr)

    records = parse_report(report, args.out)
    expected = args.minutes // args.checkpoint_minutes
    if len(records) != expected:
        raise RuntimeError(
            f"generated {len(records)} native timed states, expected {expected}")
    addrs = symbols(args.rom)
    for record in records:
        verify_cli_state(args.mgba, args.rom, args.out, addrs, record)
        print(f"[timed-mgba] {record['minute']:02d}m: "
              f"stage {record['stage']} room {record['room_counter']} "
              f"bosses {record['bosses_beaten']} HP {record['hp']} "
              f"-> {record['file']}")

    manifest = {
        "format": "mGBA native saveStateFile",
        "rom": args.rom.name,
        "rom_sha256": sha256(args.rom),
        "controller_sha256": sha256(
            ROOT / "scripts/quintra_balance_bot.lua"),
        "generator_sha256": sha256(Path(__file__)),
        "state_count": len(records),
        "checkpoint_interval_frames": interval_frames,
        "checkpoint_interval_minutes": args.checkpoint_minutes,
        "champion": args.champion,
        "difficulty": args.difficulty,
        "target_frame": args.target_frame,
        "startup_load_verified": len(records),
        "states": records,
    }
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    temp_manifest.replace(manifest_path)
    print(f"[timed-mgba] PASS {len(records)} native checkpoints at "
          f"{args.checkpoint_minutes}-minute intervals; all reload via mGBA -t")


if __name__ == "__main__":
    main()
