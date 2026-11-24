#!/usr/bin/env python3
"""Every hero must be able to walk after a post-boss Riftwild arrival (#236).

Leaving a defeated boss through any door used to copy that dungeon direction
onto the field spawn. A west exit on a wide screen placed the body at
(224, 60), which on some seeds sits inside trees or water. The cartridge now
uses the carved center landing and nudges to the nearest clear footprint.
"""
from __future__ import annotations

from pathlib import Path

from make_stage_states import (
    BGT_DOOR, CHAMPIONS, DIR_NONE, ROOM_H, ROOM_W, STAGE_BOSS_ROOM,
    boot_to_stage, normalize_compact_source, put16, riftwild_return_screen,
    select_rom_topology, settle_room, solve_entry_puzzle, symbol_addresses,
)


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"

DIR_N, DIR_E, DIR_S, DIR_W = 0, 1, 2, 3
DIR_NAME = {DIR_N: "north", DIR_E: "east", DIR_S: "south", DIR_W: "west"}
DIR_BUTTON = {DIR_N: "up", DIR_E: "right", DIR_S: "down", DIR_W: "left"}

# Compact-arena door tiles and a body pose that already stands on the
# threshold, matching advance_to_riftwild's south-door fixture.
DIR_SETUP = {
    DIR_N: {"x": 72, "y": 0, "tiles": ((0, 9), (0, 10))},
    DIR_E: {"x": ROOM_W * 8 - 16, "y": 60, "tiles": ((8, ROOM_W - 1), (9, ROOM_W - 1))},
    DIR_S: {"x": 72, "y": ROOM_H * 8 - 16, "tiles": ((ROOM_H - 1, 9), (ROOM_H - 1, 10))},
    DIR_W: {"x": 0, "y": 60, "tiles": ((8, 0), (9, 0))},
}

REPRO_SEED = 2064128583
SWEEP_SEEDS = (0x51A6D00D, 0xCAFE1234)


def get16(pyboy, address: int) -> int:
    return pyboy.memory[address] | (pyboy.memory[address + 1] << 8)


def poke_seed(pyboy, rs: int, seed: int) -> None:
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pyboy.memory[rs + 2 + i] = byte


def exit_defeated_boss(pyboy, addrs: dict[str, int], after_stage: int,
                       direction: int) -> None:
    """Rewind to a cleared boss and leave through ``direction``."""
    rs, player = addrs["_run_state"], addrs["_player"]
    entities, tilemap = addrs["_entities"], addrs["_room_tilemap"]
    setup = DIR_SETUP[direction]
    solve_entry_puzzle(pyboy, addrs)
    target = STAGE_BOSS_ROOM[after_stage - 1]
    if pyboy.memory[rs + 11] != after_stage:
        raise RuntimeError(f"Riftwild progression drifted after stage {after_stage}")
    pyboy.memory[rs + 1] = target
    pyboy.memory[rs + 6] = DIR_NONE
    pyboy.memory[rs + 10] = 0
    pyboy.memory[rs + 12] = pyboy.memory[rs + 13] = 0
    pyboy.memory[rs + 17] = 0
    pyboy.memory[rs + 18] = pyboy.memory[rs + 19] = 0
    pyboy.memory[rs + 20] = 0
    pyboy.memory[rs + 21] = pyboy.memory[rs + 22] = 0
    normalize_compact_source(pyboy, addrs)
    for i in range(32):
        entity = entities + i * 28
        if pyboy.memory[entity] == 2:
            pyboy.memory[entity] = pyboy.memory[entity + 1] = 0
    for ty, tx in setup["tiles"]:
        pyboy.memory[tilemap + ty * ROOM_W + tx] = BGT_DOOR
    source_tiles = bytes(
        pyboy.memory[tilemap + i] for i in range(ROOM_W * ROOM_H)
    )
    put16(pyboy, player + 9, setup["x"])
    put16(pyboy, player + 11, setup["y"])
    pyboy.button_press(DIR_BUTTON[direction])
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 17]:
                break
    finally:
        pyboy.button_release(DIR_BUTTON[direction])
    expected_screen = riftwild_return_screen(after_stage)
    if (not pyboy.memory[rs + 17]
            or pyboy.memory[rs + 18] != expected_screen
            or pyboy.memory[rs + 1] != target):
        raise RuntimeError(
            f"could not enter Riftwild after stage {after_stage} "
            f"via {DIR_NAME[direction]} "
            f"(world={pyboy.memory[rs + 17]} screen={pyboy.memory[rs + 18]} "
            f"room={pyboy.memory[rs + 1]})")
    for _ in range(240):
        if (pyboy.memory[addrs["_room_world_width"]] == 248
                and pyboy.memory[addrs["_room_world_height"]] == 248):
            break
        pyboy.tick()
    else:
        raise RuntimeError("Riftwild transaction never installed wide bounds")
    settle_room(pyboy, tilemap, reject_tiles=source_tiles)
    pyboy.memory[player + 2] = pyboy.memory[player + 1]


def hero_can_walk(pyboy, addrs: dict[str, int]) -> tuple[bool, int, int]:
    player = addrs["_player"]
    x0, y0 = get16(pyboy, player + 9), get16(pyboy, player + 11)
    for button in ("up", "down", "left", "right"):
        pyboy.button_press(button)
        try:
            for _ in range(24):
                pyboy.tick()
        finally:
            pyboy.button_release(button)
        pyboy.tick(2)
        if get16(pyboy, player + 9) != x0 or get16(pyboy, player + 11) != y0:
            return True, x0, y0
    return False, x0, y0


def assert_source_contracts(root: Path) -> None:
    room = (root / "src/game/room.c").read_text()
    setpiece = (root / "src/game/riftwild_setpiece.c").read_text()
    collision = (root / "src/game/room_collision.c").read_text()
    assert "from_boss_world ? DIR_NONE : dir" in room, \
        "boss-to-world exits must drop entered_from so the center landing is used"
    assert "room_player_nudge_to_clear" in collision, \
        "missing nudge-to-nearest-clear fallback"
    assert "world_screen == 8" in setpiece and "world_screen == 21" in setpiece, \
        "return-landing reservation must cover screens 8 and 21, not only 0"


def run_case(pyboy, addrs, after_stage: int, direction: int, seed: int,
             champion: str) -> None:
    poke_seed(pyboy, addrs["_run_state"], seed)
    exit_defeated_boss(pyboy, addrs, after_stage, direction)
    walked, x, y = hero_can_walk(pyboy, addrs)
    entered = pyboy.memory[addrs["_run_state"] + 6]
    label = (f"{champion} seed=0x{seed:08X} after_stage={after_stage} "
             f"{DIR_NAME[direction]} at ({x}, {y}) entered_from={entered:#x}")
    assert walked, f"soft-lock: cannot walk after {label}"
    # The transition itself should use the center landing, not a field edge.
    assert entered == DIR_NONE, f"entered_from was not cleared on {label}"


def main() -> None:
    assert_source_contracts(ROOT)
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    cases = 0
    # Repro from #236: Easy Sauran, seed 2064128583, stage-2 exit. Run every
    # hero through every door on that seed and field.
    for class_id, champion in enumerate(CHAMPIONS):
        pyboy, _ram, _room = boot_to_stage(ROM, addrs, 2, "easy", class_id)
        try:
            for direction in (DIR_N, DIR_E, DIR_S, DIR_W):
                run_case(pyboy, addrs, 2, direction, REPRO_SEED, champion)
                cases += 1
        finally:
            pyboy.stop(save=False)
    # Broader sweep: remaining return screens, two more seeds, west (the
    # historically embedding door) and south (the usual bot path).
    for seed in SWEEP_SEEDS:
        for after_stage in (1, 2, 3):
            for class_id, champion in enumerate(CHAMPIONS):
                pyboy, _ram, _room = boot_to_stage(
                    ROM, addrs, after_stage, "easy", class_id)
                try:
                    for direction in (DIR_W, DIR_S):
                        run_case(pyboy, addrs, after_stage, direction,
                                 seed, champion)
                        cases += 1
                finally:
                    pyboy.stop(save=False)
    print(f"[boss-exit-landing] PASS {cases} arrivals "
          f"(5 heroes × 4 doors on seed {REPRO_SEED} after stage 2; "
          f"west+south on stages 1-3 × 2 seeds)")


if __name__ == "__main__":
    main()
