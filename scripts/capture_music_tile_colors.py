#!/usr/bin/env python3
"""Capture before/after screenshots of a rune-sequence room.

Usage:
  python3 scripts/capture_music_tile_colors.py OUT_DIR
  python3 scripts/capture_music_tile_colors.py OUT_DIR --before ROM
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import test_puzzles as puzzles  # noqa: E402

BGT_SWITCH = 33


def bind_rom(rom: Path) -> None:
    """Point test_puzzles at a ROM and rebind tilemap/kind addresses from its .noi."""
    rom = rom.resolve()
    noi_path = rom.with_suffix(".noi")
    noi = noi_path.read_text()
    puzzles.ROM = rom
    puzzles.NOI = noi
    # generated_room / boot helpers read this module-level path, not puzzles.ROM.
    import test_stage_archetypes as archetypes
    import os
    os.environ["QUINTRA_TEST_ROM"] = str(rom)
    archetypes.ROM = rom

    def addr(name):
        match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", noi)
        if not match:
            raise RuntimeError(f"{name} missing in {noi_path}")
        return int(match.group(1), 16)

    (puzzles.RS, puzzles.PL, puzzles.EN, puzzles.TM, puzzles.KIND,
     puzzles.LOCKED, puzzles.COMBAT, puzzles.WORLD_W, puzzles.WORLD_H) = map(
        addr, (
            "_run_state", "_player", "_entities", "_room_tilemap",
            "_room_puzzle_kind", "_room_puzzle_locked", "_room_combat_sealed",
            "_room_world_width", "_room_world_height",
        ))


def scale(img):
    return img.convert("RGB").resize((480, 432), 0)


def snap(pb, out, name):
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    scale(pb.screen.image).save(path)
    print(f"wrote {path}")


def find_plates(pb):
    plates = puzzles.find_rune_plates(pb)
    if plates:
        return plates
    return [(x, y) for y in range(1, 16) for x in range(1, 19)
            if pb.memory[puzzles.TM + y * 20 + x] == BGT_SWITCH]


def capture_room(prefix, out, stage_role):
    if stage_role == "stage2-trial":
        pb = puzzles.load(2)
        addrs = None
        label = "stage2-trial"
    else:
        try:
            pb, addrs = puzzles.load_rune_room(0, "waystone")
        except RuntimeError:
            # Baseline ROMs predate room_rune_* symbols.
            from quintra_topology import dungeon_size, mission_graph
            from test_stage_archetypes import generated_room
            seed = 0x51A6D00D
            cell = mission_graph(dungeon_size(0), seed, 0)["waystone"]
            pb = generated_room(0, seed=seed, local_room=cell, keep_running=True)
        label = "stage1-waystone"
    for _ in range(60):
        pb.tick()
    snap(pb, out, f"{prefix}{label}-idle")
    plates = find_plates(pb)
    print(f"{label} plates={plates}")
    frames = [scale(pb.screen.image.copy())]
    if plates:
        # Walk each plate so the voiced flash (and, after, pitch colour) is visible.
        for plate in plates:
            puzzles.feet_on(pb, *plate)
            for _ in range(16):
                frames.append(scale(pb.screen.image.copy()))
                pb.tick()
            snap(pb, out, f"{prefix}{label}-voiced")
    if len(frames) > 1:
        gif = out / f"{prefix}{label}-voice.gif"
        frames[0].save(gif, save_all=True, append_images=frames[1:],
                       duration=80, loop=0)
        print(f"wrote {gif} ({len(frames)} frames)")
    pb.stop(save=False)


def main():
    out = Path(sys.argv[1])
    if len(sys.argv) > 3 and sys.argv[2] == "--before":
        prefix = "before_"
        bind_rom(Path(sys.argv[3]))
    else:
        prefix = "after_"
        bind_rom(puzzles.ROM)
    capture_room(prefix, out, "stage2-trial")
    capture_room(prefix, out, "stage1-waystone")


if __name__ == "__main__":
    main()
