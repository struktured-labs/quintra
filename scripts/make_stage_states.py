#!/usr/bin/env python3
"""Create deterministic, progression-aware PyBoy checkpoints for Quintra.

The fixtures are external developer saves, never cartridge saves.  Each one
boots a blank-SRAM cartridge, uses the real title/class/dungeon-entry flow,
adds a deterministic version of the guaranteed prior-boss reward curve, and
publishes stage-entry, pre-boss sanctuary, live-boss, post-boss Riftwild, and
village checkpoints in a manifest binding ROM, emulator version, filename,
and state hash.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from importlib.metadata import version
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, VILLAGE_ROOM, dungeon_size,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
ROOM_W, ROOM_H = 20, 17
BGT_PORTAL = 34
BGT_DOOR = 3
BGT_BOSS_GATE_L = 72
BGT_BOSS_GATE_R = 73
ZELDA_CELL_DUNGEON_ENTRANCE = 6
SCREEN_ROOM = 5
DIR_NONE = 0xFF
BLANK_SRAM_BYTES = 32 * 1024
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def select_rom_topology(rom: Path) -> None:
    """Keep the mandatory pre-build checkpoint pass valid across the ABI seam.

    The preamble intentionally exercises the currently linked ROM before a new
    one is produced. Presence of the new topology helper in that ROM's linker
    symbols is stronger evidence than source version text.
    """
    global STAGE_START, STAGE_BOSS_ROOM, VILLAGE_ROOM
    symbols = rom.with_suffix(".noi").read_text()
    image = rom.read_bytes()
    if "DEF _run_state_boss_room " not in symbols:
        STAGE_START = (0, 7, 13, 20, 25, 31, 38, 43, 49)
        STAGE_BOSS_ROOM = (6, 12, 18, 24, 30, 36, 42, 48, 54)
        VILLAGE_ROOM = {3: 19, 6: 37}
    elif b"v0.18.55" in image:
        # v0.18.55 introduced explicit topology and the wide Compass, then
        # the next milestone enlarged that topology again after playtesting.
        # The mandatory pre-link checkpoint pass must still understand the
        # one known intermediate ROM. Newer versions retain the expanded
        # 10..16-room layout and must not fall back merely because their title
        # string changed.
        STAGE_START = (0, 7, 15, 25, 34, 44, 55, 66, 77)
        STAGE_BOSS_ROOM = (6, 14, 23, 33, 43, 53, 65, 76, 88)
        VILLAGE_ROOM = {3: 24, 6: 54}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_addresses(rom: Path) -> dict[str, int]:
    noi = rom.with_suffix(".noi")
    text = noi.read_text()
    result: dict[str, int] = {}
    for name in ("_run_state", "_player", "_entities", "_room_tilemap",
                 "_loop_current_screen", "_room_puzzle_kind",
                 "_room_puzzle_locked"):
        match = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", text)
        if not match:
            raise RuntimeError(f"missing ROM symbol {name} in {noi}")
        result[name] = int(match.group(1), 16)
    return result


def new_emulator(rom: Path) -> tuple[PyBoy, io.BytesIO]:
    """Boot with explicit blank in-memory SRAM, independent of local saves."""
    ram = io.BytesIO(bytes(BLANK_SRAM_BYTES))
    return PyBoy(str(rom), window="null", cgb=True, ram_file=ram), ram


def put16(pyboy: PyBoy, address: int, value: int) -> None:
    pyboy.memory[address] = value & 0xFF
    pyboy.memory[address + 1] = (value >> 8) & 0xFF


def stage_entry_room(stage: int) -> int:
    """Return the first actual combat room for zero-based stage ``stage``."""
    # A fresh title flow already owns room 0; synthetic deep-stage entry uses
    # a portal transaction and therefore targets room 1 for the tutorial.
    return 1 if stage == 0 else STAGE_START[stage]


def dungeon_cell_xy(cell: int) -> tuple[int, int]:
    row, offset = divmod(cell, 4)
    return ((3 - offset) if row & 1 else offset), row


def graph_direction(source: int, target: int) -> str:
    sx, sy = dungeon_cell_xy(source)
    tx, ty = dungeon_cell_xy(target)
    delta = tx - sx, ty - sy
    return {
        (0, -1): "up", (1, 0): "right",
        (0, 1): "down", (-1, 0): "left",
    }[delta]


def cross_graph_edge(pyboy: PyBoy, player: int, tilemap: int, direction: str) -> None:
    """Place the synthetic fixture at one real reciprocal graph threshold."""
    if direction == "up":
        put16(pyboy, player + 9, 72); put16(pyboy, player + 11, 0)
        pyboy.memory[tilemap + 9] = pyboy.memory[tilemap + 10] = BGT_DOOR
    elif direction == "right":
        put16(pyboy, player + 9, 144); put16(pyboy, player + 11, 60)
        pyboy.memory[tilemap + 8 * 20 + 19] = BGT_DOOR
        pyboy.memory[tilemap + 9 * 20 + 19] = BGT_DOOR
    elif direction == "down":
        put16(pyboy, player + 9, 72); put16(pyboy, player + 11, 120)
        pyboy.memory[tilemap + 16 * 20 + 9] = BGT_DOOR
        pyboy.memory[tilemap + 16 * 20 + 10] = BGT_DOOR
    else:
        put16(pyboy, player + 9, 0); put16(pyboy, player + 11, 60)
        pyboy.memory[tilemap + 8 * 20] = BGT_DOOR
        pyboy.memory[tilemap + 9 * 20] = BGT_DOOR
    pyboy.button_press(direction)


def apply_prior_progression(pyboy: PyBoy, rs: int, player: int, stage: int) -> None:
    """Model the guaranteed build curve earned before this stage.

    A real boss gives one of three class-attuned combat relics.  The fixed
    PowerStone/Swift Fang/VampSigil cycle is intentionally representative,
    deterministic, and never stronger than collecting the same live drops.
    """
    rewards = (22, 27, 29)
    hp_max = pyboy.memory[player + 1]
    atk = pyboy.memory[player + 5]
    spd = pyboy.memory[player + 7]
    for i in range(stage):
        item = rewards[i % len(rewards)]
        pyboy.memory[player + 24 + i] = item
        if item == 22:  # PowerStone: +1 ATK
            atk = min(15, atk + 1)
        elif item == 27:  # Swift Fang: +1 ATK, +1 SPD
            atk = min(15, atk + 1)
            spd = min(9, spd + 1)
        else:  # VampSigil: +1 ATK, +1 max HP
            atk = min(15, atk + 1)
            hp_max = min(30, hp_max + 1)
    pyboy.memory[player + 1] = hp_max
    pyboy.memory[player + 2] = hp_max
    pyboy.memory[player + 5] = atk
    pyboy.memory[player + 7] = spd
    put16(pyboy, player + 16, min(999, stage * 8))
    pyboy.memory[rs + 9] = min(255, stage * 4)   # rooms cleared
    put16(pyboy, rs + 14, min(65535, stage * 750))
    pyboy.memory[rs + 16] = min(255, stage * 12)  # enemies killed


def settle_room(pyboy: PyBoy, tilemap: int, *, normalize_scroll: bool = True) -> None:
    """Wait until CGB uploads and the stage-entry fade have committed."""
    previous = None
    stable = 0
    for _ in range(240):
        pyboy.tick()
        tiles = bytes(pyboy.memory[tilemap + i] for i in range(ROOM_W * ROOM_H))
        lcd_on = bool(pyboy.memory[0xFF40] & 0x80)
        # A streamed Zelda-style transition installs the destination's logical
        # tilemap before its blocking scroll routine has returned. Tile bytes
        # can therefore be stable while the LCD still shows two half-rooms.
        # Publish only after both hardware scroll registers are normalized.
        scroll_ready = (not normalize_scroll
                        or (pyboy.memory[0xFF43] == 0
                            and pyboy.memory[0xFF42] == 0))
        committed = not any(tile & 0x80 for tile in tiles) and scroll_ready
        stable = stable + 1 if lcd_on and committed and tiles == previous else 0
        previous = tiles
        if stable >= 10:
            return
    raise RuntimeError("stage room did not settle within 240 frames")


def _puzzle_feet_on(pyboy: PyBoy, player: int, tx: int, ty: int) -> None:
    put16(pyboy, player + 9, tx * 8 - 8)
    put16(pyboy, player + 11, ty * 8 - 12)
    for _ in range(3):
        pyboy.tick()


def solve_entry_puzzle(pyboy: PyBoy, addrs: dict[str, int]) -> None:
    """Resolve a locked entry fixture through its live interaction contract.

    Checkpoint/gallery setup may position the champion, but it never clears
    the lock bit or solved bit directly: the cartridge must observe the cairn
    move or the correct ordered rune contacts and release its own doors.
    """
    player = addrs["_player"]
    tilemap = addrs["_room_tilemap"]
    kind = pyboy.memory[addrs["_room_puzzle_kind"]]
    locked = addrs["_room_puzzle_locked"]
    if not pyboy.memory[locked]:
        return
    if kind == 1:  # PUZZLE_PUSH_SEAL
        blocks = [(x, y) for y in range(1, ROOM_H - 1)
                  for x in range(1, ROOM_W - 1)
                  if pyboy.memory[tilemap + y * ROOM_W + x] == 25]
        if len(blocks) != 1:
            raise RuntimeError(f"push puzzle expected one cairn, got {blocks}")
        bx, by = blocks[0]
        put16(pyboy, player + 9, bx * 8 - 16)
        put16(pyboy, player + 11, by * 8 - 8)
        pyboy.button_press("right")
        try:
            for _ in range(120):
                pyboy.tick()
                if not pyboy.memory[locked]:
                    return
        finally:
            pyboy.button_release("right")
    elif kind == 2:  # PUZZLE_RUNE_SEQUENCE
        runes = [(x, y) for y in range(1, ROOM_H - 1)
                 for x in range(1, ROOM_W - 1)
                 if pyboy.memory[tilemap + y * ROOM_W + x] == 33]
        if len(runes) != 3:
            raise RuntimeError(f"rune puzzle expected three runes, got {runes}")

        def off() -> None:
            _puzzle_feet_on(pyboy, player, 10, 13)

        first = None
        for rune in runes:
            _puzzle_feet_on(pyboy, player, *rune)
            if pyboy.memory[tilemap + rune[1] * ROOM_W + rune[0]] == 19:
                first = rune
                off()
                break
            off()
        if first is None:
            raise RuntimeError("rune puzzle exposed no valid first tone")

        second = None
        for rune in runes:
            if rune == first:
                continue
            # A failed candidate resets the sequence, so replay the known
            # first contact before testing the next one.
            if pyboy.memory[tilemap + first[1] * ROOM_W + first[0]] != 19:
                _puzzle_feet_on(pyboy, player, *first)
                off()
            _puzzle_feet_on(pyboy, player, *rune)
            if (pyboy.memory[tilemap + first[1] * ROOM_W + first[0]] == 19
                    and pyboy.memory[tilemap + rune[1] * ROOM_W + rune[0]] == 19):
                second = rune
                off()
                break
            off()
        if second is None:
            raise RuntimeError("rune puzzle exposed no valid second tone")
        third = next(rune for rune in runes if rune not in (first, second))
        _puzzle_feet_on(pyboy, player, *third)
        off()
        if not pyboy.memory[locked]:
            return
    raise RuntimeError(f"could not solve entry puzzle kind {kind}")


def advance_to_sanctuary(pyboy: PyBoy, addrs: dict[str, int], stage: int) -> int:
    """Enter the real full-heal room immediately before this stage's boss.

    The fixture crosses an ordinary north threshold from the prior room so
    the cartridge generates the sanctuary, marked forward gate, stage music,
    and return edge itself. The saved player arrives at the south side, before
    the proximity roar; walking north exercises the entire warning contract.
    """
    rs, player = addrs["_run_state"], addrs["_player"]
    entities, tilemap = addrs["_entities"], addrs["_room_tilemap"]
    solve_entry_puzzle(pyboy, addrs)
    target = STAGE_BOSS_ROOM[stage] - 1
    pyboy.memory[rs + 1] = target - 1
    pyboy.memory[rs + 6] = 0xFF  # DIR_NONE before the synthetic approach
    put16(pyboy, rs + 23,
          (pyboy.memory[rs + 23] | pyboy.memory[rs + 24] << 8) | (1 << stage))
    pyboy.memory[rs + 27] |= 1 << 3
    if dungeon_size(stage) >= 12:
        pyboy.memory[rs + 27] |= 1 << 7
    if dungeon_size(stage) >= 14:
        pyboy.memory[rs + 28] |= 1 << 7
    for i in range(32):
        entity = entities + i * 28
        if pyboy.memory[entity] == 2:
            pyboy.memory[entity] = pyboy.memory[entity + 1] = 0
    source_local = target - 1 - STAGE_START[stage]
    target_local = target - STAGE_START[stage]
    direction = graph_direction(source_local, target_local)
    cross_graph_edge(pyboy, player, tilemap, direction)
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 1] == target:
                break
    finally:
        pyboy.button_release(direction)
    if pyboy.memory[rs + 1] != target:
        raise RuntimeError(f"could not enter sanctuary {stage + 1}")
    settle_room(pyboy, tilemap)
    return target


def advance_to_boss(pyboy: PyBoy, addrs: dict[str, int], stage: int) -> int:
    """Cross the sanctuary's real marked north gate into the live boss.

    This is developer-fixture setup, like the progression curve above: WRAM is
    arranged outside the shipped ROM only to position the hero at the already
    generated threshold. Ordinary controller/transition code generates the
    actual encounter with its authored music, palette, body, and build.
    """
    rs, player = addrs["_run_state"], addrs["_player"]
    tilemap = addrs["_room_tilemap"]
    target = STAGE_BOSS_ROOM[stage]
    if pyboy.memory[rs + 1] != target - 1:
        raise RuntimeError(f"boss {stage + 1} fixture did not begin in sanctuary")
    put16(pyboy, rs + 23,
          (pyboy.memory[rs + 23] | pyboy.memory[rs + 24] << 8) | (1 << stage))
    pyboy.memory[rs + 27] |= 1 << 3
    if dungeon_size(stage) >= 12:
        pyboy.memory[rs + 27] |= 1 << 7
    if dungeon_size(stage) >= 14:
        pyboy.memory[rs + 28] |= 1 << 7
    source_local = target - 1 - STAGE_START[stage]
    target_local = target - STAGE_START[stage]
    direction = graph_direction(source_local, target_local)
    cross_graph_edge(pyboy, player, tilemap, direction)
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 1] == target:
                break
    finally:
        pyboy.button_release(direction)
    if pyboy.memory[rs + 1] != target:
        raise RuntimeError(f"could not enter boss {stage + 1}")
    # Boss bodies deliberately breathe through bounded camera motion; unlike
    # a streamed room transition, their nonzero scroll is finished gameplay.
    settle_room(pyboy, tilemap, normalize_scroll=False)
    pyboy.memory[player + 2] = pyboy.memory[player + 1]
    return target


def advance_to_village(pyboy: PyBoy, addrs: dict[str, int],
                       after_stage: int) -> int:
    """Build a real arrival-square checkpoint after dungeon 3 or 6.

    A normal defeated boss exits through Riftwild before reaching town, so a
    village fixture cannot merely rename a dungeon entry state. Arrange the
    pre-town counter, cross its ordinary east threshold, then visit the market
    and return. That final round-trip regenerates the arrival with the real
    post-region palette, music, residents, civic exits, and upcoming build.
    """
    if after_stage not in (3, 6):
        raise ValueError("villages exist only after stages 3 and 6")
    rs, player = addrs["_run_state"], addrs["_player"]
    entities, tilemap = addrs["_entities"], addrs["_room_tilemap"]
    target = VILLAGE_ROOM[after_stage]
    # Villages are reached from the post-boss Riftwild gate, not from a fake
    # linear dungeon counter. Recreate that real portal transaction: the gate
    # calls begin_dungeon(), increments the defeated boss room into the fixed
    # town counter, and loads all civic presentation through cartridge code.
    pyboy.memory[rs + 1] = STAGE_BOSS_ROOM[after_stage - 1]
    pyboy.memory[rs + 11] = after_stage
    pyboy.memory[rs + 17] = 1
    pyboy.memory[rs + 18] = 6
    pyboy.memory[rs + 19] = 0
    pyboy.memory[rs + 6] = 0xFF
    for i in range(32):
        entity = entities + i * 28
        if pyboy.memory[entity] == 2:
            pyboy.memory[entity] = pyboy.memory[entity + 1] = 0
    pyboy.memory[tilemap + 8 * ROOM_W + 10] = 34  # BGT_PORTAL
    put16(pyboy, player + 9, 72)
    put16(pyboy, player + 11, 52)
    for _ in range(120):
        pyboy.tick()
        if pyboy.memory[rs + 1] == target and not pyboy.memory[rs + 17]:
            break
    if pyboy.memory[rs + 1] != target or pyboy.memory[rs + 19] != 0:
        raise RuntimeError(f"could not enter village after stage {after_stage}")
    settle_room(pyboy, tilemap)

    # Arrival east -> market.
    put16(pyboy, player + 9, 144)
    put16(pyboy, player + 11, 60)
    pyboy.button_press("right")
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 19] == 1:
                break
    finally:
        pyboy.button_release("right")
    if pyboy.memory[rs + 19] != 1:
        raise RuntimeError(f"village {after_stage // 3} market edge is broken")
    settle_room(pyboy, tilemap)

    # Market west -> correctly themed arrival square.
    put16(pyboy, player + 9, 0)
    put16(pyboy, player + 11, 60)
    pyboy.button_press("left")
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 19] == 0:
                break
    finally:
        pyboy.button_release("left")
    if pyboy.memory[rs + 19] != 0:
        raise RuntimeError(f"village {after_stage // 3} return edge is broken")
    settle_room(pyboy, tilemap)
    pyboy.memory[player + 2] = pyboy.memory[player + 1]
    return target


def advance_to_riftwild(pyboy: PyBoy, addrs: dict[str, int],
                        after_stage: int) -> int:
    """Cross a defeated boss room's real south door into Riftwild screen 0.

    ``boot_to_stage(after_stage)`` has already installed the build and boss
    count earned through that dungeon. Rewind only the visible room counter to
    the defeated boss, clear its dead encounter table, and take the same
    cardinal exit a player uses. The cartridge itself initializes fog of war,
    generates the outdoor roster/terrain, places the hero, and selects music.
    """
    if not 1 <= after_stage <= 8:
        raise ValueError("Riftwild checkpoints exist only after stages 1 through 8")
    rs, player = addrs["_run_state"], addrs["_player"]
    entities, tilemap = addrs["_entities"], addrs["_room_tilemap"]
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
    for i in range(32):
        entity = entities + i * 28
        if pyboy.memory[entity] == 2:
            pyboy.memory[entity] = pyboy.memory[entity + 1] = 0
    pyboy.memory[tilemap + (ROOM_H - 1) * ROOM_W + 9] = BGT_DOOR
    pyboy.memory[tilemap + (ROOM_H - 1) * ROOM_W + 10] = BGT_DOOR
    put16(pyboy, player + 9, 72)
    put16(pyboy, player + 11, 120)
    pyboy.button_press("down")
    try:
        for _ in range(120):
            pyboy.tick()
            if pyboy.memory[rs + 17]:
                break
    finally:
        pyboy.button_release("down")
    if (not pyboy.memory[rs + 17] or pyboy.memory[rs + 18] != 0
            or pyboy.memory[rs + 1] != target):
        raise RuntimeError(f"could not enter Riftwild after stage {after_stage}")
    settle_room(pyboy, tilemap)
    pyboy.memory[player + 2] = pyboy.memory[player + 1]
    return target


def boot_to_stage(rom: Path, addrs: dict[str, int], stage: int,
                  difficulty: str, class_id: int) -> tuple[PyBoy, io.BytesIO, int]:
    """Enter a qualified stage through the live cartridge's dungeon gate."""
    rs, player = addrs["_run_state"], addrs["_player"]
    entities, tilemap = addrs["_entities"], addrs["_room_tilemap"]
    pyboy, ram = new_emulator(rom)
    pyboy.tick(240)
    pyboy.button("start")
    pyboy.tick(30)
    for _ in range(class_id):
        pyboy.button("down")
        pyboy.tick(8)
    if difficulty == "easy":
        pyboy.button("select")
        pyboy.tick(8)
    pyboy.button("a")
    pyboy.tick(60)

    target = stage_entry_room(stage)
    pyboy.memory[rs + 1] = target - 1
    for i, byte in enumerate((0x51A6D00D).to_bytes(4, "little")):
        pyboy.memory[rs + 2 + i] = byte
    pyboy.memory[rs + 11] = stage
    pyboy.memory[rs + 12] = 0
    pyboy.memory[rs + 13] = 0
    put16(pyboy, rs + 23, (1 << stage) - 1)
    pyboy.memory[rs + 17] = 1
    pyboy.memory[rs + 18] = ZELDA_CELL_DUNGEON_ENTRANCE
    pyboy.memory[rs + 19] = 0
    pyboy.memory[rs + 20] = 0
    pyboy.memory[rs + 21] = pyboy.memory[rs + 22] = 0
    pyboy.memory[rs + 25] = 0
    pyboy.memory[rs + 26] = 1 if difficulty == "easy" else 0
    apply_prior_progression(pyboy, rs, player, stage)
    for i in range(32):
        entity = entities + i * 28
        if pyboy.memory[entity] == 2:
            pyboy.memory[entity] = pyboy.memory[entity + 1] = 0
    put16(pyboy, player + 9, 72)
    put16(pyboy, player + 11, 60)
    pyboy.memory[tilemap + 9 * ROOM_W + 10] = BGT_PORTAL

    for _ in range(90):
        pyboy.tick()
        if pyboy.memory[rs + 1] == target and not pyboy.memory[rs + 17]:
            break
    if pyboy.memory[rs + 1] != target or pyboy.memory[rs + 17]:
        pyboy.stop(save=False)
        raise RuntimeError(f"could not enter stage {stage + 1} ({difficulty})")
    settle_room(pyboy, tilemap)
    return pyboy, ram, target


def verify_state(rom: Path, addrs: dict[str, int], path: Path,
                 stage: int, room: int, difficulty: str,
                 checkpoint: str, class_id: int) -> None:
    """Prove a published checkpoint is immediately playable after restore."""
    rs, player = addrs["_run_state"], addrs["_player"]
    screen = addrs["_loop_current_screen"]
    pyboy, ram = new_emulator(rom)
    with path.open("rb") as saved:
        pyboy.load_state(saved)
    is_riftwild = checkpoint == "riftwild"
    checks = {
        "room": pyboy.memory[rs + 1] == room,
        "stage": pyboy.memory[rs + 11] == stage,
        "world_context": bool(pyboy.memory[rs + 17]) == is_riftwild,
        "screen": pyboy.memory[screen] == SCREEN_ROOM,
        "alive": pyboy.memory[player + 2] > 0,
        "difficulty": pyboy.memory[rs + 26] == (difficulty == "easy"),
        "champion": pyboy.memory[player] == class_id,
        "x": 0 <= (pyboy.memory[player + 9] | pyboy.memory[player + 10] << 8) <= 144,
        "y": 0 <= (pyboy.memory[player + 11] | pyboy.memory[player + 12] << 8) <= 120,
    }
    if checkpoint == "riftwild":
        entities = addrs["_entities"]
        seen = pyboy.memory[rs + 21] | pyboy.memory[rs + 22] << 8
        checks["post_boss_room"] = room == STAGE_BOSS_ROOM[stage - 1]
        checks["arrival_screen"] = pyboy.memory[rs + 18] == 0
        checks["fresh_fog"] = seen == 1
        checks["no_giant"] = not any(
            pyboy.memory[entities + i * 28] == 2
            and pyboy.memory[entities + i * 28 + 1] & 1
            and pyboy.memory[entities + i * 28 + 20] & 1
            for i in range(32))
    elif checkpoint == "boss":
        entities = addrs["_entities"]
        checks["live_boss"] = any(
            pyboy.memory[entities + i * 28] == 2
            and pyboy.memory[entities + i * 28 + 1] & 1
            and pyboy.memory[entities + i * 28 + 20] & 1
            for i in range(32))
    elif checkpoint == "sanctuary":
        entities = addrs["_entities"]
        checks["sanctuary_room"] = room == STAGE_BOSS_ROOM[stage] - 1
        checks["safe"] = not any(
            pyboy.memory[entities + i * 28] == 2
            and pyboy.memory[entities + i * 28 + 1] & 1
            for i in range(32))
        checks["full_hp"] = pyboy.memory[player + 2] == pyboy.memory[player + 1]
        checks["full_mp"] = pyboy.memory[player + 4] == pyboy.memory[player + 3]
        checks["sigil"] = bool((pyboy.memory[rs + 23]
                                 | pyboy.memory[rs + 24] << 8) & (1 << stage))
        pyboy.memory[0xFF4F] = 0
        # A spatial dungeon can approach its last snake cell from either of
        # two reciprocal edges. Verify the complete projected seal anywhere
        # on the visible BG rather than assuming every threshold is north.
        visible = [pyboy.memory[0x9800 + y * 32 + x]
                   for y in range(18) for x in range(20)]
        checks["marked_gate"] = all(tile in visible for tile in range(
            BGT_BOSS_GATE_L, BGT_BOSS_GATE_L + 4))
    elif checkpoint == "village":
        checks["village_room"] = room in VILLAGE_ROOM.values()
        checks["arrival_square"] = pyboy.memory[rs + 19] == 0
        checks["safe"] = not any(
            pyboy.memory[addrs["_entities"] + i * 28] == 2
            and pyboy.memory[addrs["_entities"] + i * 28 + 1] & 1
            for i in range(32))
    pyboy.stop(save=False)
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"{path.name}: unplayable checkpoint ({', '.join(failed)})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=ROOT / "tmp/stage-states")
    parser.add_argument("--stage", type=int, action="append", dest="stages",
                        help="human stage number (1 through 9); repeatable")
    parser.add_argument("--difficulty", choices=("normal", "easy"), action="append",
                        help="mode to generate; repeatable (default: both)")
    parser.add_argument("--champion", choices=CHAMPIONS, action="append",
                        help="champion to generate; repeatable (default: all five)")
    args = parser.parse_args()
    args.rom = args.rom.resolve()
    select_rom_topology(args.rom)
    stages = args.stages or list(range(1, 10))
    difficulties = args.difficulty or ["normal", "easy"]
    champions = args.champion or list(CHAMPIONS)
    if any(stage < 1 or stage > 9 for stage in stages):
        parser.error("--stage must be between 1 and 9")

    addrs = symbol_addresses(args.rom)
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for champion in dict.fromkeys(champions):
        class_id = CHAMPIONS.index(champion)
        for number in sorted(set(stages)):
            for difficulty in dict.fromkeys(difficulties):
                stage = number - 1
                pyboy, ram, room = boot_to_stage(
                    args.rom, addrs, stage, difficulty, class_id)
                suffix = "" if difficulty == "normal" else "-easy"
                for checkpoint in ("entry", "sanctuary", "boss"):
                    if checkpoint == "sanctuary":
                        room = advance_to_sanctuary(pyboy, addrs, stage)
                    elif checkpoint == "boss":
                        room = advance_to_boss(pyboy, addrs, stage)
                    state_path = args.out / (
                        f"quintra-stage-{number:02d}-{checkpoint}-"
                        f"{champion}{suffix}.pyboy")
                    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
                    with temp_path.open("wb") as saved:
                        pyboy.save_state(saved)
                    temp_path.replace(state_path)
                    verify_state(args.rom, addrs, state_path, stage, room,
                                 difficulty, checkpoint, class_id)
                    records.append({
                        "stage": number,
                        "room_counter": room,
                        "difficulty": difficulty,
                        "checkpoint": checkpoint,
                        "class_id": class_id,
                        "champion": champion,
                        "file": state_path.name,
                        "sha256": sha256(state_path),
                    })
                    print(f"[stage-states] {champion} stage {number} "
                          f"{difficulty} {checkpoint}: {state_path}")
                pyboy.stop(save=False)

        # Direct outdoor arrivals make the Zelda/Ultima traversal and its
        # compact Compass testable without first replaying a Colossus. There
        # is no post-final Riftwild: stage nine correctly enters the ending.
        for after_stage in range(1, 9):
            if after_stage not in stages:
                continue
            for difficulty in dict.fromkeys(difficulties):
                # The next-stage boot gives this fixture the exact relic/stat
                # curve and bosses_beaten value earned after the requested
                # boss; advance_to_riftwild then crosses the real old boss exit.
                pyboy, ram, _ = boot_to_stage(
                    args.rom, addrs, after_stage, difficulty, class_id)
                room = advance_to_riftwild(pyboy, addrs, after_stage)
                suffix = "" if difficulty == "normal" else "-easy"
                state_path = args.out / (
                    f"quintra-riftwild-after-stage-{after_stage:02d}-"
                    f"{champion}{suffix}.pyboy")
                temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
                with temp_path.open("wb") as saved:
                    pyboy.save_state(saved)
                temp_path.replace(state_path)
                verify_state(args.rom, addrs, state_path, after_stage, room,
                             difficulty, "riftwild", class_id)
                records.append({
                    "stage": after_stage + 1,
                    "after_stage": after_stage,
                    "room_counter": room,
                    "difficulty": difficulty,
                    "checkpoint": "riftwild",
                    "class_id": class_id,
                    "champion": champion,
                    "file": state_path.name,
                    "sha256": sha256(state_path),
                })
                print(f"[stage-states] {champion} Riftwild after stage "
                      f"{after_stage} {difficulty}: {state_path}")
                pyboy.stop(save=False)

        # Two explicit civic checkpoints answer the human-testing question
        # "put me at the village" without forcing a stage/boss state to stand
        # in for a different context. STAGE=3/6 still selects the pre-village
        # boss; CHECKPOINT=village selects the following arrival square.
        for after_stage in (3, 6):
            if after_stage not in stages:
                continue
            for difficulty in dict.fromkeys(difficulties):
                pyboy, ram, _ = boot_to_stage(
                    args.rom, addrs, after_stage, difficulty, class_id)
                room = advance_to_village(pyboy, addrs, after_stage)
                suffix = "" if difficulty == "normal" else "-easy"
                state_path = args.out / (
                    f"quintra-village-after-stage-{after_stage:02d}-"
                    f"{champion}{suffix}.pyboy")
                temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
                with temp_path.open("wb") as saved:
                    pyboy.save_state(saved)
                temp_path.replace(state_path)
                verify_state(args.rom, addrs, state_path, after_stage, room,
                             difficulty, "village", class_id)
                records.append({
                    "stage": after_stage + 1,
                    "after_stage": after_stage,
                    "village": after_stage // 3,
                    "room_counter": room,
                    "difficulty": difficulty,
                    "checkpoint": "village",
                    "class_id": class_id,
                    "champion": champion,
                    "file": state_path.name,
                    "sha256": sha256(state_path),
                })
                print(f"[stage-states] {champion} village {after_stage // 3} "
                      f"after stage {after_stage} {difficulty}: {state_path}")
                pyboy.stop(save=False)

    manifest = {
        "format": "PyBoy save_state",
        "pyboy_version": version("pyboy"),
        "rom": args.rom.name,
        "rom_sha256": sha256(args.rom),
        "seed": "0x51A6D00D",
        "progression": "deterministic prior-boss reward curve",
        "states": records,
    }
    manifest_path = args.out / "manifest.json"
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    temp_manifest.replace(manifest_path)
    print(f"[stage-states] verified {len(records)} external PyBoy checkpoint(s)")


if __name__ == "__main__":
    main()
