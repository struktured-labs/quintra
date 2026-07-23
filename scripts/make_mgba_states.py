#!/usr/bin/env python3
"""Generate and verify native mGBA checkpoints for hands-on deep testing."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
DEFAULT_OUT = ROOT / "tmp/mgba-states"
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
CHECKPOINTS = ("entry", "sanctuary", "boss", "riftwild", "village")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbols(rom: Path) -> dict[str, int]:
    text = rom.with_suffix(".noi").read_text()
    result = {}
    for name in ("_run_state", "_player", "_entities", "_room_tilemap",
                 "_loop_current_screen"):
        match = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", text)
        if not match:
            raise RuntimeError(f"missing {name} in {rom.with_suffix('.noi')}")
        result[name] = int(match.group(1), 16)
    return result


def wait_for_marker(process: subprocess.Popen, path: Path, marker: str,
                    timeout: float, log_path: Path | None = None) -> str:
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(errors="replace")
            if marker in text:
                break
        if process.poll() is not None:
            break
        time.sleep(0.05)
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    if marker not in text:
        log = (log_path.read_text(errors="replace")
               if log_path and log_path.exists() else "")
        raise RuntimeError(
            f"mGBA exited with {process.returncode} without producing "
            f"{marker!r} in {path}:\n{text}\n{log}")
    return text


def launch_generator(mgba: str, rom: Path, out: Path, addrs: dict[str, int],
                     champion: str, difficulty: str) -> list[dict]:
    class_id = CHAMPIONS.index(champion)
    report = out / f".{champion}-{difficulty}.tsv"
    report.unlink(missing_ok=True)
    save_dir = out / ".sram" / f"{champion}-{difficulty}"
    save_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "QUINTRA_MGBA_STATE_DIR": str(out),
        "QUINTRA_MGBA_STATE_REPORT": str(report),
        "QUINTRA_RS_ADDR": str(addrs["_run_state"]),
        "QUINTRA_PL_ADDR": str(addrs["_player"]),
        "QUINTRA_EN_ADDR": str(addrs["_entities"]),
        "QUINTRA_TM_ADDR": str(addrs["_room_tilemap"]),
        "QUINTRA_SCREEN_ADDR": str(addrs["_loop_current_screen"]),
        "QUINTRA_STATE_CLASS": str(class_id),
        "QUINTRA_STATE_CHAMPION": champion,
        "QUINTRA_STATE_DIFFICULTY": difficulty,
    })
    log_path = out / f".{champion}-{difficulty}.log"
    with log_path.open("wb", buffering=0) as log:
        process = subprocess.Popen([
            mgba, "-C", f"savegamePath={save_dir}", str(rom),
            "--script", str(ROOT / "scripts/make_mgba_states.lua"), "-l", "127",
        ], env=env, stdout=log, stderr=subprocess.STDOUT)
        text = wait_for_marker(process, report, "DONE\n", 120, log_path)
    records = []
    for line in text.splitlines():
        if not line or line == "DONE":
            continue
        filename, checkpoint, stage, after_stage, room, mode, class_text, world = (
            line.split("\t"))
        state = out / filename
        if not state.is_file() or state.stat().st_size < 1024:
            raise RuntimeError(f"mGBA state is missing or truncated: {state}")
        records.append({
            "file": filename,
            "checkpoint": checkpoint,
            "stage": int(stage),
            "after_stage": int(after_stage),
            "room_counter": int(room),
            "difficulty": mode,
            "class_id": int(class_text),
            "champion": champion,
            "world_mode": int(world),
            "bytes": state.stat().st_size,
            "sha256": sha256(state),
        })
    if len(records) != 37:
        raise RuntimeError(
            f"{champion} {difficulty} produced {len(records)} states, expected 37")
    return records


def verify_cli_state(mgba: str, rom: Path, out: Path, addrs: dict[str, int],
                     record: dict) -> None:
    result = out / ".verify-result"
    result.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update({
        "QUINTRA_MGBA_VERIFY_OUT": str(result),
        "QUINTRA_RS_ADDR": str(addrs["_run_state"]),
        "QUINTRA_PL_ADDR": str(addrs["_player"]),
        "QUINTRA_SCREEN_ADDR": str(addrs["_loop_current_screen"]),
        "QUINTRA_EXPECT_ROOM": str(record["room_counter"]),
        # The public bosses_beaten byte is zero-based for dungeon checkpoints
        # and equals after_stage for outdoor/village checkpoints.
        "QUINTRA_EXPECT_STAGE": str(
            record["after_stage"] if record["checkpoint"] in ("riftwild", "village")
            else record["stage"] - 1),
        "QUINTRA_EXPECT_WORLD": str(record["world_mode"]),
        "QUINTRA_EXPECT_CLASS": str(record["class_id"]),
        "QUINTRA_EXPECT_DIFFICULTY": str(record["difficulty"] == "easy" and 1 or 0),
    })
    log_path = out / ".verify.log"
    with log_path.open("wb", buffering=0) as log:
        process = subprocess.Popen([
            mgba, "-t", str(out / record["file"]), str(rom),
            "--script", str(ROOT / "scripts/verify_mgba_state.lua"), "-l", "127",
        ], env=env, stdout=log, stderr=subprocess.STDOUT)
        wait_for_marker(process, result, "PASS\n", 30, log_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--mgba", default=os.environ.get(
        "QUINTRA_MGBA_BIN", "mgba-headless"))
    parser.add_argument("--champion", choices=CHAMPIONS, action="append",
                        help="repeatable; defaults to all five")
    parser.add_argument("--difficulty", choices=("normal", "easy"), action="append",
                        help="repeatable; defaults to both")
    args = parser.parse_args()
    args.rom = args.rom.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    champions = tuple(dict.fromkeys(args.champion or CHAMPIONS))
    difficulties = tuple(dict.fromkeys(
        args.difficulty or ("normal", "easy")))
    addrs = symbols(args.rom)

    records = []
    for champion in champions:
        for difficulty in difficulties:
            generated = launch_generator(
                args.mgba, args.rom, args.out, addrs, champion, difficulty)
            records.extend(generated)
            print(f"[mgba-states] {champion} {difficulty}: "
                  f"{len(generated)} native checkpoints")

    # Prove command-line startup loading, not only same-process API restore,
    # for every checkpoint family represented in this requested set.
    for checkpoint in CHECKPOINTS:
        record = next(r for r in records if r["checkpoint"] == checkpoint)
        verify_cli_state(args.mgba, args.rom, args.out, addrs, record)

    manifest = {
        "format": "mGBA native saveStateFile",
        "rom": args.rom.name,
        "rom_sha256": sha256(args.rom),
        "generator_sha256": sha256(ROOT / "scripts/make_mgba_states.lua"),
        "state_count": len(records),
        "champions": list(champions),
        "difficulties": list(difficulties),
        "progression": "deterministic prior-boss reward curve",
        "startup_load_verified": list(CHECKPOINTS),
        "states": records,
    }
    manifest_path = args.out / "manifest.json"
    temp = manifest_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n")
    temp.replace(manifest_path)
    print(f"[mgba-states] PASS {len(records)} native states; "
          f"five checkpoint families reload through mGBA -t")


if __name__ == "__main__":
    main()
