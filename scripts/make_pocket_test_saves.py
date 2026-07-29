#!/usr/bin/env python3
"""Build Analogue Pocket test ROM/save pairs from Quintra checkpoints.

Pocket openFPGA cores cannot consume PyBoy or mGBA emulator snapshots. Quintra
does not need them: its battery-backed suspend record contains the run seed,
progression, champion, build, and current room, and regenerates the room when
the title's CONTINUE action is selected.

This tool extracts that portable payload from the hash-bound PyBoy curriculum,
serializes Quintra's real 32 KiB cartridge SRAM format, and gives every
checkpoint a separately named ROM/save pair. The mirrored Assets/Saves tree is
ready to merge into an Analogue Pocket SD card without replacing a player's
ordinary Quintra ROM or save.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
DEFAULT_STATES = ROOT / "tmp/stage-states"
DEFAULT_OUT = ROOT / "tmp/pocket-test-saves"

RUN_STATE_SIZE = 36
PLAYER_STATE_SIZE = 42
SRAM_SIZE = 32 * 1024
# budude2.GBC stores a 16-byte RTC trailer after cartridge RAM even for this
# MBC5 (non-RTC) cart. Quintra ignores it, but emitting the native file length
# avoids asking Pocket OS to resize a preloaded save on first launch. The
# canonical empty trailer is ten zero data bytes plus six unused 0xFF bytes.
POCKET_TRAILER = bytes(10) + bytes((0xFF,)) * 6
SCREEN_ROOM = 5
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
STAGE_NAMES = (
    "Crystal Caverns",
    "Verdant Hollow",
    "Ember Depths",
    "Frost Vault",
    "Toxic Mire",
    "Shadow Keep",
    "Golden Temple",
    "Bloodmoon",
    "Void Sanctum",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rom_version(rom: Path) -> str:
    match = re.search(rb"v[0-9]+\.[0-9]+\.[0-9]+", rom.read_bytes())
    return match.group().decode("ascii") if match else rom.stem


def symbol_address(rom: Path, name: str) -> int:
    match = re.search(
        rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)",
        rom.with_suffix(".noi").read_text(),
    )
    if not match:
        raise RuntimeError(f"missing ROM symbol {name}")
    return int(match.group(1), 16)


def suspend_sram(run_state: bytes, player: bytes) -> bytes:
    if len(run_state) != RUN_STATE_SIZE:
        raise ValueError(f"run-state size drifted: {len(run_state)}")
    if len(player) != PLAYER_STATE_SIZE:
        raise ValueError(f"player-state size drifted: {len(player)}")
    payload = run_state + player
    record = b"QS" + bytes((1, len(run_state), len(player)))
    record += payload + bytes((sum(payload) & 0xFF,))
    sram = bytearray(SRAM_SIZE)
    sram[:len(record)] = record
    return bytes(sram)


def extract_payload(
    rom: Path,
    state_path: Path,
    run_state_address: int,
    player_address: int,
) -> tuple[bytes, bytes]:
    pyboy = PyBoy(
        str(rom),
        window="null",
        cgb=True,
        ram_file=io.BytesIO(bytes(SRAM_SIZE)),
    )
    try:
        with state_path.open("rb") as state:
            pyboy.load_state(state)
        run_state = bytes(
            pyboy.memory[run_state_address + i] for i in range(RUN_STATE_SIZE)
        )
        player = bytes(
            pyboy.memory[player_address + i] for i in range(PLAYER_STATE_SIZE)
        )
        return run_state, player
    finally:
        pyboy.stop(save=False)


def press(pyboy: PyBoy, button: str, held: int = 4, released: int = 4) -> None:
    pyboy.button_press(button)
    pyboy.tick(held)
    pyboy.button_release(button)
    pyboy.tick(released)


def verify_resume(
    rom: Path,
    sram: bytes,
    run_state_address: int,
    player_address: int,
    screen_address: int,
    record: dict,
) -> None:
    battery = io.BytesIO(sram)
    pyboy = PyBoy(str(rom), window="null", cgb=True, ram_file=battery)
    try:
        pyboy.tick(240)
        press(pyboy, "a")
        for _ in range(360):
            pyboy.tick()
            if pyboy.memory[screen_address] == SCREEN_ROOM:
                break

        observed = {
            "screen": pyboy.memory[screen_address],
            "room": pyboy.memory[run_state_address + 1],
            "stage": pyboy.memory[run_state_address + 11],
            "difficulty": pyboy.memory[run_state_address + 26],
            "champion": pyboy.memory[player_address],
            "hp": pyboy.memory[player_address + 2],
        }
        expected = {
            "screen": SCREEN_ROOM,
            "room": record["room_counter"],
            "stage": record["stage"] - 1,
            "difficulty": int(record["difficulty"] == "easy"),
            "champion": record["class_id"],
        }
        failed = [
            key for key, value in expected.items() if observed[key] != value
        ]
        if observed["hp"] <= 0:
            failed.append("hp")
        if failed:
            raise RuntimeError(
                f"{record['file']}: cold resume failed {failed}; "
                f"observed={observed}, expected={expected}"
            )
    finally:
        pyboy.stop(save=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--states", type=Path, default=DEFAULT_STATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--difficulty",
        choices=("normal", "easy"),
        default="easy",
        help="Pocket test curriculum (default: easy)",
    )
    parser.add_argument(
        "--checkpoint",
        choices=("entry", "court", "sanctuary", "boss"),
        default="entry",
        help="checkpoint family to export (default: entry)",
    )
    parser.add_argument(
        "--champion",
        choices=CHAMPIONS,
        action="append",
        help="champion to export; repeatable (default: all five)",
    )
    parser.add_argument(
        "--stage",
        type=int,
        action="append",
        help="human stage number 1..9; repeatable (default: all nine)",
    )
    parser.add_argument(
        "--pocket-template-save",
        type=Path,
        help="optional Pocket .sav whose post-SRAM trailer should be retained",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip cold-booting every generated SRAM image in PyBoy",
    )
    args = parser.parse_args()

    rom = args.rom.resolve()
    states = args.states.resolve()
    out = args.out.resolve()
    version = rom_version(rom)
    manifest = json.loads((states / "manifest.json").read_text())
    if manifest["rom_sha256"] != sha256(rom):
        raise RuntimeError(
            "checkpoint manifest does not belong to the requested ROM: "
            f"{manifest['rom_sha256']} != {sha256(rom)}"
        )

    champions = set(args.champion or CHAMPIONS)
    stages = set(args.stage or range(1, 10))
    if any(stage < 1 or stage > 9 for stage in stages):
        parser.error("--stage must be between 1 and 9")

    selected = [
        record for record in manifest["states"]
        if record["checkpoint"] == args.checkpoint
        and record["difficulty"] == args.difficulty
        and record["champion"] in champions
        and record["stage"] in stages
    ]
    selected.sort(key=lambda item: (item["stage"], item["class_id"]))
    expected_count = len(champions) * len(stages)
    if len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} matching states, found {len(selected)}"
        )

    run_state_address = symbol_address(rom, "_run_state")
    player_address = symbol_address(rom, "_player")
    screen_address = symbol_address(rom, "_loop_current_screen")

    trailer = POCKET_TRAILER
    if args.pocket_template_save:
        template = args.pocket_template_save.read_bytes()
        if len(template) < SRAM_SIZE:
            raise RuntimeError("Pocket template save is smaller than 32 KiB")
        trailer = template[SRAM_SIZE:]

    relative_dir = Path("Quintra Test Checkpoints")
    rom_dir = out / "Assets/gbc/common" / relative_dir
    save_dir = out / "Saves/gbc/common" / relative_dir
    if out.exists():
        shutil.rmtree(out)
    rom_dir.mkdir(parents=True)
    save_dir.mkdir(parents=True)

    generated = []
    for record in selected:
        state_path = states / record["file"]
        if sha256(state_path) != record["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch: {state_path}")

        run_state, player = extract_payload(
            rom, state_path, run_state_address, player_address
        )
        sram = suspend_sram(run_state, player)
        if not args.no_verify:
            verify_resume(
                rom,
                sram,
                run_state_address,
                player_address,
                screen_address,
                record,
            )

        champion = record["champion"].title()
        base = (
            f"QTEST S{record['stage']:02d} {champion} "
            f"{record['difficulty'].title()}"
        )
        rom_path = rom_dir / f"{base}.gbc"
        save_path = save_dir / f"{base}.sav"
        shutil.copyfile(rom, rom_path)
        save_path.write_bytes(sram + trailer)
        generated.append({
            "stage": record["stage"],
            "stage_name": STAGE_NAMES[record["stage"] - 1],
            "champion": record["champion"],
            "difficulty": record["difficulty"],
            "checkpoint": record["checkpoint"],
            "room_counter": record["room_counter"],
            "rom": str(rom_path.relative_to(out)),
            "save": str(save_path.relative_to(out)),
            "rom_sha256": sha256(rom_path),
            "save_sha256": sha256(save_path),
            "sram_sha256": sha256_bytes(sram),
            "pocket_trailer_bytes": len(trailer),
        })
        print(
            f"[pocket] S{record['stage']:02d} {champion:<8} "
            f"{record['difficulty']} -> room {record['room_counter']}"
        )

    readme = out / "QUINTRA-TEST-CHECKPOINTS.txt"
    readme.write_text(
        f"Quintra {version} Analogue Pocket test checkpoints\n"
        "==================================================\n\n"
        "Open the budude2 GBC core, enter the Quintra Test Checkpoints folder,\n"
        "and choose a QTEST ROM. At the Quintra title screen press A for\n"
        "CONTINUE (do not press START, which begins a new run and replaces\n"
        "that test ROM's independent suspend save).\n\n"
        "Each ROM is the exact release cartridge; only its paired battery\n"
        "save differs. The player's ordinary Quintra-v0.18.90.gbc save is\n"
        "not read or changed. These checkpoints use Easy mode for practical\n"
        "deep-stage testing and include all five champions at every stage.\n"
    )
    output_manifest = {
        "format": "Analogue Pocket mirrored ROM/battery-save curriculum",
        "source_manifest": str((states / "manifest.json").resolve()),
        "rom": rom.name,
        "version": version,
        "rom_sha256": sha256(rom),
        "checkpoint": args.checkpoint,
        "difficulty": args.difficulty,
        "count": len(generated),
        "records": generated,
    }
    (out / "manifest.json").write_text(
        json.dumps(output_manifest, indent=2) + "\n"
    )
    print(
        f"[pocket] PASS {len(generated)} cold-resumable test pairs in {out}"
    )


if __name__ == "__main__":
    main()
