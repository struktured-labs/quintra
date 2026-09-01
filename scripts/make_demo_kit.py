#!/usr/bin/env python3
"""Build four cold-resumable Analogue Pocket stations for a short demo."""
from __future__ import annotations

import argparse
import io
import json
import shutil
from pathlib import Path

from pyboy import PyBoy

from make_pocket_test_saves import (
    POCKET_TRAILER,
    PLAYER_STATE_SIZE,
    RUN_STATE_SIZE,
    SCREEN_ROOM,
    extract_payload,
    press,
    rom_version,
    sha256,
    sha256_bytes,
    suspend_sram,
    symbol_address,
    verify_resume,
)
from test_shop_surge import PL as SHOP_PLAYER
from test_shop_surge import ROM as SHOP_ROM
from test_shop_surge import boot_shop, shop_wares


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
DEFAULT_STATES = ROOT / "tmp/stage-states"
DEFAULT_OUT = ROOT / "builds/quintra-demo-kit"
WARE_BOOMERANG = 18


def curriculum_record(manifest: dict, checkpoint: str) -> dict:
    matches = [
        record for record in manifest["states"]
        if record["champion"] == "wolfkin"
        and record["difficulty"] == "normal"
        and record["checkpoint"] == checkpoint
        and (record.get("after_stage", record["stage"]) == 1)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one stage-one {checkpoint}, found {len(matches)}")
    return matches[0]


def merchant_payload(rom: Path) -> tuple[bytes, bytes]:
    if rom != SHOP_ROM.resolve():
        raise RuntimeError("merchant fixture requires rom/working/quintra.gbc")
    pyboy = boot_shop(36)
    try:
        assert WARE_BOOMERANG in shop_wares(pyboy)
        pyboy.memory[SHOP_PLAYER + 2] = pyboy.memory[SHOP_PLAYER + 1]
        pyboy.memory[SHOP_PLAYER + 4] = pyboy.memory[SHOP_PLAYER + 3]
        pyboy.memory[SHOP_PLAYER + 16] = 99
        pyboy.memory[SHOP_PLAYER + 17] = 0
        pyboy.memory[SHOP_PLAYER + 19] = 80
        run = bytes(pyboy.memory[symbol_address(rom, "_run_state") + i]
                    for i in range(RUN_STATE_SIZE))
        player = bytes(pyboy.memory[SHOP_PLAYER + i]
                       for i in range(PLAYER_STATE_SIZE))
        return run, player
    finally:
        pyboy.stop(save=False)


def verify_merchant(rom: Path, sram: bytes) -> None:
    screen = symbol_address(rom, "_loop_current_screen")
    player = symbol_address(rom, "_player")
    entities = symbol_address(rom, "_entities")
    pyboy = PyBoy(str(rom), window="null", cgb=True, ram_file=io.BytesIO(sram))
    try:
        pyboy.tick(240)
        press(pyboy, "a")
        for _ in range(360):
            pyboy.tick()
            if pyboy.memory[screen] == SCREEN_ROOM:
                break
        pyboy.tick(120)
        wares = {
            pyboy.memory[entities + i * 28 + 18]
            for i in range(32)
            if pyboy.memory[entities + i * 28] == 3
            and pyboy.memory[entities + i * 28 + 17] == 4
        }
        assert pyboy.memory[screen] == SCREEN_ROOM
        assert WARE_BOOMERANG in wares, f"resumed merchant stock was {sorted(wares)}"
        assert pyboy.memory[player + 16] >= 30
    finally:
        pyboy.stop(save=False)


def write_pair(out: Path, rom: Path, name: str, sram: bytes) -> dict:
    relative = Path("Quintra Demo")
    rom_dir = out / "Assets/gbc/common" / relative
    save_dir = out / "Saves/gbc/common" / relative
    rom_dir.mkdir(parents=True, exist_ok=True)
    save_dir.mkdir(parents=True, exist_ok=True)
    rom_path = rom_dir / f"{name}.gbc"
    save_path = save_dir / f"{name}.sav"
    shutil.copyfile(rom, rom_path)
    save_path.write_bytes(sram + POCKET_TRAILER)
    return {
        "name": name,
        "rom": str(rom_path.relative_to(out)),
        "save": str(save_path.relative_to(out)),
        "rom_sha256": sha256(rom_path),
        "save_sha256": sha256(save_path),
        "sram_sha256": sha256_bytes(sram),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--states", type=Path, default=DEFAULT_STATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rom = args.rom.resolve()
    states = args.states.resolve()
    out = args.out.resolve()
    manifest = json.loads((states / "manifest.json").read_text())
    if manifest["rom_sha256"] != sha256(rom):
        raise RuntimeError("checkpoint manifest does not match the demo ROM")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    run_address = symbol_address(rom, "_run_state")
    player_address = symbol_address(rom, "_player")
    screen_address = symbol_address(rom, "_loop_current_screen")
    stations = []
    for name, checkpoint in (
        ("QDEMO 1 FIRST ROOM", "entry"),
        ("QDEMO 3 CRYSTAL BOSS", "boss"),
        ("QDEMO 4 RIFTWILD", "riftwild"),
    ):
        record = curriculum_record(manifest, checkpoint)
        state = states / record["file"]
        if sha256(state) != record["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch: {state}")
        run, player = extract_payload(rom, state, run_address, player_address)
        sram = suspend_sram(run, player)
        verify_resume(rom, sram, run_address, player_address, screen_address, record)
        stations.append(write_pair(out, rom, name, sram))

    run, player = merchant_payload(rom)
    merchant_sram = suspend_sram(run, player)
    verify_merchant(rom, merchant_sram)
    stations.insert(1, write_pair(
        out, rom, "QDEMO 2 BOOMERANG SHOP", merchant_sram))

    version = rom_version(rom)
    digest = sha256(rom)
    (out / "DEMO-RUNBOOK.txt").write_text(
        f"Quintra {version} demo kit\n"
        f"ROM SHA-256: {digest}\n\n"
        "Copy Assets and Saves to the Pocket SD root. Launch a QDEMO ROM,\n"
        "then press A for CONTINUE. START deliberately erases that station.\n\n"
        "Recommended flow:\n"
        "  1 FIRST ROOM       fresh Wolfkin combat and dash\n"
        "  2 BOOMERANG SHOP   buy the 30-coin Boomerang, then press B\n"
        "  3 CRYSTAL BOSS     high-contrast first Colossus\n"
        "  4 RIFTWILD         open-world traversal and theme\n\n"
        "Pitch: A new Game Boy Color roguelike with five monster heroes,\n"
        "procedural Zelda-like dungeons, and bullet-hell Colossi.\n\n"
        "Controls: D-pad move/aim; A primary; B hero power/boomerang;\n"
        "A+B Oath Art; double-tap D-pad dash; START Pack; SELECT Compass.\n"
    )
    output = {
        "version": version,
        "rom_sha256": digest,
        "format": "Analogue Pocket mirrored ROM/battery-save demo kit",
        "stations": stations,
    }
    (out / "manifest.json").write_text(json.dumps(output, indent=2) + "\n")
    print(f"[demo-kit] PASS {len(stations)} cold-resumable stations in {out}")


if __name__ == "__main__":
    main()
