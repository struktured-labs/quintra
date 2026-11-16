#!/usr/bin/env python3
"""Live-ROM contract for the Riftwild hidden dens.

Covers each den gate (CAIRN stone, DROWNED pond island, Hollow-only SCAR
sinkhole island), den completion and its reward, claim persistence across
backtracking, a dungeon trip and a power cycle, the Compass reveal, the Echo
Chime hint state, and that every den room keeps a way home (no softlock).
"""
import io
import os
import re
from collections import deque
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_DENS_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()

ENTITY_SIZE = 28
ENT_ENEMY, ENT_PICKUP = 2, 3
PICKUP_ITEM = 3
RIFT_BOMB_ID = 40   # items[22]
ECHO_CHIME_ID = 41  # items[23]
FLOOR, DOOR, PILLAR, BLOCK, PORTAL = 1, 3, 21, 25, 34
WATER, STONE, HOLE = 97, 98, 108
MAP_CACHE = 122
WIDE = 31
DEN_BASE = 36
# run_state / player byte offsets (see run_state.h / player.h).
RS_ROOM, RS_BOSSES, RS_WMODE, RS_WSCREEN, RS_WRET = 1, 11, 17, 18, 19
RS_XXHI, RS_SHADOW = 50, 57
PL_X, PL_Y, PL_INV, PL_WAYGEAR = 9, 11, 24, 44
GLOVE, RAFT, HOOK = 1, 2, 4
HOLLOW = 0x01
# Region 0 placement: field, kind, den slot (riftwild_den.c).
CAIRN_FIELD, DROWNED_FIELD, SCAR_FIELD = 7, 14, 25
STAT_ITEMS = range(10, 20)   # vigor..heart: dens never grant permanent stats


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(
    addr, ("_run_state", "_player", "_entities", "_room_tilemap",
           "_procgen_current_room_is_large", "_room_world_width",
           "_room_world_height", "_room_camera_x", "_room_camera_y"))
EXT = addr("_room_world_extension")
BOTTOM = addr("_room_world_bottom")
SCREEN = addr("_loop_current_screen")


def put16(pb, where, value):
    pb.memory[where] = value & 255
    pb.memory[where + 1] = (value >> 8) & 255


def tick(pb, frames=90):
    for _ in range(frames):
        pb.tick()


def hold(pb, button, frames):
    pb.button_press(button)
    tick(pb, frames)
    pb.button_release(button)
    tick(pb, 2)


def at(pb, x, y):
    put16(pb, PL + PL_X, x)
    put16(pb, PL + PL_Y, y)


def feet_on(pb, tx, ty):
    """Stand so the movement feet probe lands on tile (tx, ty)."""
    at(pb, tx * 8 - 8, ty * 8 - 12)


def wide_tile(pb, x, y):
    if y < 17:
        return pb.memory[TM + y * 20 + x] & 0x7F if x < 20 else \
            pb.memory[EXT + y * 11 + (x - 20)] & 0x7F
    return pb.memory[BOTTOM + (y - 17) * WIDE + x] & 0x7F


def room_tile(pb, x, y):
    return pb.memory[TM + y * 20 + x]


def ws(pb):
    return pb.memory[RS + RS_WSCREEN]


def entities(pb, kind):
    out = []
    for index in range(32):
        e = EN + index * ENTITY_SIZE
        if pb.memory[e] == kind and pb.memory[e + 1] & 1:
            out.append(e)
    return out


def teleport_field(pb, field):
    """Use the field's own portal handler: a portal tile under the feet with
    world_screen pre-set regenerates that field (dev shortcut only)."""
    pb.memory[RS + RS_WSCREEN] = field
    at(pb, 72, 60)
    pb.memory[TM + 9 * 20 + 10] = PORTAL
    tick(pb, 150)
    assert ws(pb) == field and pb.memory[WORLD_W] == 248, \
        f"teleport to field {field} failed (ws={ws(pb)})"


WALKABLE = {35, 36, 96, 105, 106, 107, 1, 4, 5, 18, 19, PORTAL}


def reachable(pb, goal, passable_extra=()):
    """Tile BFS over the 31x31 field from its center arrival point."""
    ok = WALKABLE | set(passable_extra)
    start = (15, 15)
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        if (x, y) == goal:
            return True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < WIDE and 0 <= ny < WIDE and (nx, ny) not in seen \
                    and wide_tile(pb, nx, ny) in ok:
                seen.add((nx, ny))
                queue.append((nx, ny))
    return False


def enter_riftwild(pb):
    tick(pb, 240)
    pb.button("start"); tick(pb, 30)
    pb.button("a"); tick(pb, 90)
    pb.memory[RS + RS_ROOM] = STAGE_BOSS_ROOM[0]
    pb.memory[RS + RS_BOSSES] = 1
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[TM + 16 * 20 + 9] = DOOR
    pb.memory[TM + 16 * 20 + 10] = DOOR
    at(pb, 72, 120)
    tick(pb, 180)
    assert pb.memory[RS + RS_WMODE] == 1 and ws(pb) == 0, "Riftwild handoff failed"


def assert_den_room(pb, screen):
    assert ws(pb) == screen, f"expected den screen {screen}, got {ws(pb)}"
    # The harness skips real fights; keep the hero alive between rooms.
    pb.memory[PL + 2] = pb.memory[PL + 1]
    assert pb.memory[WORLD_W] == 160 and pb.memory[LARGE] == 0, \
        "den rooms must be compact"
    # Every den room after the first keeps its west door open: no softlock.
    if (screen - DEN_BASE) % 4:
        assert room_tile(pb, 0, 8) == DOOR and room_tile(pb, 0, 9) == DOOR, \
            f"den room {screen} lost its way back"


def no_stat_rewards(pb):
    for e in entities(pb, ENT_PICKUP):
        if pb.memory[e + 17] == PICKUP_ITEM:
            assert pb.memory[e + 18] not in STAT_ITEMS, "den granted a stat item"


def calm(pb):
    """Remove field enemies so knockback cannot shove the hero off a mark."""
    for e in entities(pb, ENT_ENEMY):
        pb.memory[e + 1] = 0


def snap(pb, frames, key, tx=20, ty=22):
    """Frame the den clearing (fields are wider than the screen)."""
    if pb.memory[WORLD_W] == 248:
        feet_on(pb, tx, ty)
        tick(pb, 150)   # the field camera eases toward the hero
    frames[key] = pb.screen.image.copy()


def crate(pb):
    for y in range(17):
        for x in range(20):
            if room_tile(pb, x, y) == BLOCK:
                return x, y
    return None


def push_crate(pb, button, goal, gif):
    """Hold a direction until the crate's top-left tile reaches goal."""
    pb.button_press(button)
    last = crate(pb)
    for _ in range(600):
        pb.tick()
        now = crate(pb)
        if now != last:
            gif.append(pb.screen.image.copy())
            last = now
        if now == goal:
            break
    pb.button_release(button)
    tick(pb, 4)
    assert crate(pb) == goal, f"crate stuck at {crate(pb)} pushing {button} to {goal}"


def cairn(pb, frames):
    teleport_field(pb, CAIRN_FIELD)
    snap(pb, frames, "cairn_sealed")
    assert wide_tile(pb, 24, 22) == STONE, "CAIRN tell stone missing"
    assert not reachable(pb, (24, 22)), "sealed stair must not be reachable"
    assert not pb.memory[RS + RS_XXHI] & 0x10

    # Wolfkin without the Glove cannot shift the stone.
    calm(pb)
    feet_on(pb, 23, 22)
    hold(pb, "right", 90)
    assert wide_tile(pb, 24, 22) == STONE, "stone opened without its gate"

    # Compass hides undiscovered dens.
    pb.memory[PL + PL_WAYGEAR] |= GLOVE
    calm(pb)
    feet_on(pb, 23, 22)
    tick(pb, 60)
    gif = [pb.screen.image.copy()]
    pb.button_press("right")
    for step in range(180):
        pb.tick()
        if step % 4 == 0:
            gif.append(pb.screen.image.copy())
        if wide_tile(pb, 24, 22) == PORTAL:
            break
    pb.button_release("right")
    for _ in range(8):
        tick(pb, 4)
        gif.append(pb.screen.image.copy())
    frames["cairn_open_gif"] = gif
    assert wide_tile(pb, 24, 22) == PORTAL, "Glove did not open the cairn"
    assert ws(pb) == CAIRN_FIELD
    frames["cairn_open"] = pb.screen.image.copy()

    feet_on(pb, 24, 22)
    tick(pb, 150)
    assert_den_room(pb, DEN_BASE)
    assert pb.memory[RS + RS_XXHI] & 0x10, "found bit not recorded"
    assert pb.memory[RS + RS_WRET] & 0x3F == CAIRN_FIELD
    frames["cairn_entry"] = pb.screen.image.copy()

    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 1)
    assert room_tile(pb, 5, 11) == BLOCK, "puzzle crate missing"
    assert room_tile(pb, 15, 8) == PILLAR, "alcove must start sealed"
    assert not pb.memory[RS + RS_SHADOW] & 0x10

    # Real crate pushes: up seven tiles, then right six onto the socket.
    gif = []
    gif.append(pb.screen.image.copy())
    at(pb, 40, 104)
    push_crate(pb, "up", (5, 4), gif)
    at(pb, 26, 24)
    push_crate(pb, "right", (11, 4), gif)
    tick(pb, 30); gif.append(pb.screen.image.copy())
    frames["cairn_puzzle_gif"] = gif
    assert room_tile(pb, 11, 4) == BLOCK, (
        "crate did not reach the socket: "
        + " ".join(f"{x},{y}" for y in range(17) for x in range(20)
                   if room_tile(pb, x, y) == BLOCK))
    assert room_tile(pb, 15, 8) != PILLAR, "solving did not open the alcove"
    assert room_tile(pb, 17, 12) == PORTAL, "no exit portal after the solve"
    assert pb.memory[RS + RS_SHADOW] & 0x10, "claim bit not set"
    no_stat_rewards(pb)
    frames["cairn_solved"] = pb.screen.image.copy()
    items = [e for e in entities(pb, ENT_PICKUP) if pb.memory[e + 17] == PICKUP_ITEM]
    assert items, "no tool reward"
    item = items[0]
    at(pb, pb.memory[item + 3], pb.memory[item + 7] - 8); tick(pb, 10)
    inv = bytes(pb.memory[PL + PL_INV:PL + PL_INV + 16])
    assert RIFT_BOMB_ID in inv, f"Rift Bomb reward not collected: {inv.hex()}"

    feet_on(pb, 17, 12); tick(pb, 150)
    assert ws(pb) == CAIRN_FIELD and pb.memory[WORLD_W] == 248, "exit portal failed"
    assert wide_tile(pb, 24, 22) == PORTAL, "found stair resealed"

    # Re-entry: claimed den stays solved and grants nothing twice.
    feet_on(pb, 24, 22); tick(pb, 150)
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 1)
    assert room_tile(pb, 15, 8) != PILLAR and room_tile(pb, 17, 12) == PORTAL
    assert not [e for e in entities(pb, ENT_PICKUP)
                if pb.memory[e + 17] == PICKUP_ITEM], "claimed reward respawned"


def power_cycle(pb):
    """Suspend from inside a den room and cold boot through battery SRAM."""
    ram = io.BytesIO(bytes(0x8000))
    tick(pb, 4)
    pb.stop(save=True, ram_file=ram)
    ram.seek(0)
    second = PyBoy(str(ROM), window="null", cgb=True, ram_file=ram)
    tick(second, 240)
    second.button("a"); tick(second, 90)
    assert second.memory[SCREEN] == 5, "cold boot did not resume the room"
    assert_den_room(second, DEN_BASE + 1)
    assert second.memory[RS + RS_SHADOW] & 0x10 and second.memory[RS + RS_XXHI] & 0x10
    return second


def dungeon_trip(pb):
    """Re-enter the Riftwild from the next boss: claims survive, Hollow resets."""
    pb.memory[RS + RS_SHADOW] |= HOLLOW
    pb.memory[RS + RS_WMODE] = 0
    pb.memory[RS + RS_ROOM] = STAGE_BOSS_ROOM[1]
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    for e in entities(pb, ENT_ENEMY):
        pb.memory[e + 1] = 0
    pb.memory[TM + 16 * 20 + 9] = DOOR
    pb.memory[TM + 16 * 20 + 10] = DOOR
    at(pb, 72, 120)
    tick(pb, 180)
    assert pb.memory[RS + RS_WMODE] == 1, "did not return to the Riftwild"
    shadow = pb.memory[RS + RS_SHADOW]
    assert shadow & 0x10, "den claim lost on a dungeon trip"
    assert not shadow & HOLLOW, "Hollow survived the dungeon trip"
    assert pb.memory[RS + RS_XXHI] & 0x10, "den discovery lost on a dungeon trip"


def press_until(pb, button, screen):
    pb.button_press(button)
    for _ in range(120):
        pb.tick()
        if pb.memory[SCREEN] == screen:
            break
    pb.button_release(button)
    tick(pb, 2)
    assert pb.memory[SCREEN] == screen, f"{button} did not reach screen {screen}"


def compass(pb, frames=None, key=None):
    """Found + unclaimed dens show the cache glyph; Compass otherwise silent."""
    press_until(pb, "select", 8)
    tick(pb, 60)
    if frames is not None:
        frames[key] = pb.screen.image.copy()
    vram = bytes(pb.memory[0x9800:0x9800 + 32 * 18])
    press_until(pb, "b", 5)
    tick(pb, 30)
    return vram


def drowned(pb, frames):
    teleport_field(pb, DROWNED_FIELD)
    assert wide_tile(pb, 24, 22) == PORTAL, "DROWNED stair should be open"
    assert wide_tile(pb, 21, 19) == WATER and wide_tile(pb, 27, 25) == WATER
    assert not reachable(pb, (24, 22)), "pond island reachable without water gear"
    assert reachable(pb, (24, 22), (WATER,)), "pond island unreachable with Raft"
    snap(pb, frames, "drowned_field")
    before = compass(pb)
    assert MAP_CACHE not in before, "Compass revealed an undiscovered den"

    pb.memory[PL + PL_WAYGEAR] |= RAFT
    feet_on(pb, 24, 22); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 4)
    # Leave by the entry stair, look from the next field: the found,
    # unclaimed den is now marked as loot on the Compass.
    feet_on(pb, 4, 4); tick(pb, 150)
    assert ws(pb) == DROWNED_FIELD, "den entry stair did not lead home"
    teleport_field(pb, DROWNED_FIELD - 1)
    after = compass(pb, frames, "compass_found")
    assert MAP_CACHE in after, "Compass did not mark the found den"
    teleport_field(pb, DROWNED_FIELD)
    feet_on(pb, 24, 22); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 4)
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 5)
    foes = entities(pb, ENT_ENEMY)
    assert len(foes) >= 3, f"trial room has {len(foes)} enemies"
    assert room_tile(pb, 19, 8) == PILLAR, "trial door must start sealed"
    frames["drowned_trial"] = pb.screen.image.copy()
    for e in foes:
        pb.memory[e + 1] = 0
    tick(pb, 90)
    assert room_tile(pb, 19, 8) == DOOR, "clearing the trial did not open the door"
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 6)
    assert pb.memory[RS + RS_SHADOW] & 0x20, "DROWNED claim bit not set"
    assert room_tile(pb, 15, 12) == PORTAL
    no_stat_rewards(pb)
    frames["drowned_vault"] = pb.screen.image.copy()
    feet_on(pb, 15, 12); tick(pb, 150)
    assert ws(pb) == DROWNED_FIELD
    teleport_field(pb, DROWNED_FIELD - 1)
    claimed = compass(pb)
    assert MAP_CACHE not in claimed, "claimed den still marked as loot"


def scar(pb, frames):
    pb.memory[RS + RS_SHADOW] &= ~HOLLOW & 0xFF
    teleport_field(pb, SCAR_FIELD)
    assert wide_tile(pb, 24, 22) == STONE, "Hollow-only den manifest in Waking"
    assert wide_tile(pb, 21, 19) == HOLE
    snap(pb, frames, "scar_waking")
    pb.memory[RS + RS_SHADOW] |= HOLLOW
    teleport_field(pb, SCAR_FIELD)
    assert wide_tile(pb, 24, 22) == PORTAL, "Hollow did not reveal the SCAR stair"
    assert not reachable(pb, (24, 22)), "SCAR island reachable without the Hook"
    assert reachable(pb, (24, 22), (HOLE,)), "SCAR island unreachable with Hook"
    snap(pb, frames, "scar_hollow")

    pb.memory[PL + PL_WAYGEAR] |= HOOK
    feet_on(pb, 24, 22); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 8)
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 9)
    for e in entities(pb, ENT_ENEMY):
        pb.memory[e + 1] = 0
    tick(pb, 30)
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 10)
    assert room_tile(pb, 19, 8) == PILLAR
    # Puzzle logic is covered by CAIRN; solve this one directly.
    for y in (11, 12):
        for x in (5, 6):
            pb.memory[TM + y * 20 + x] = FLOOR
    for y, row in ((4, (25, 26)), (5, (27, 28))):
        pb.memory[TM + y * 20 + 11] = row[0]
        pb.memory[TM + y * 20 + 12] = row[1]
    tick(pb, 30)
    assert room_tile(pb, 19, 8) == DOOR, "socketed crate did not open the door"
    at(pb, 144, 60); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 11)
    keeper = entities(pb, ENT_ENEMY)
    assert len(keeper) == 1, f"keeper room has {len(keeper)} enemies"
    assert pb.memory[keeper[0] + 14] > 30, "keeper is not mini-boss strength"
    frames["scar_keeper"] = pb.screen.image.copy()
    assert not pb.memory[RS + RS_SHADOW] & 0x40
    pb.memory[keeper[0] + 1] = 0
    tick(pb, 90)
    assert pb.memory[RS + RS_SHADOW] & 0x40, "keeper claim not set"
    assert room_tile(pb, 15, 12) == PORTAL, "no exit after the keeper"
    no_stat_rewards(pb)
    frames["scar_reward"] = pb.screen.image.copy()
    feet_on(pb, 15, 12); tick(pb, 150)
    assert ws(pb) == SCAR_FIELD, (
        f"keeper exit failed: ws={ws(pb)} screen={pb.memory[SCREEN]} "
        f"hp={pb.memory[PL + 2]} xy=({pb.memory[PL + PL_X]},{pb.memory[PL + PL_Y]}) "
        f"tile={room_tile(pb, 15, 12)}")


def chime(frames):
    """Echo Chime in a field with an unfound den: the Compass gains a dim
    hint (open=0, claim=1) and entering the den still pays out normally."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    enter_riftwild(pb)
    teleport_field(pb, DROWNED_FIELD)
    inv = PL + PL_INV
    slot = bytes(pb.memory[inv:inv + 16]).index(0xFF)
    pb.memory[inv + slot] = ECHO_CHIME_ID
    press_until(pb, "start", 9)
    tick(pb, 20)
    pb.button("right"); tick(pb, 20)
    press_until(pb, "a", 5)
    tick(pb, 30)
    assert pb.memory[RS + RS_SHADOW] & 0x20 and not pb.memory[RS + RS_XXHI] & 0x20, \
        "Echo Chime did not record the hint state"
    teleport_field(pb, DROWNED_FIELD - 1)
    assert MAP_CACHE in compass(pb, frames, "compass_chimed"), "no dim Compass hint"
    teleport_field(pb, DROWNED_FIELD)
    pb.memory[PL + PL_WAYGEAR] |= RAFT
    feet_on(pb, 24, 22); tick(pb, 150)
    assert_den_room(pb, DEN_BASE + 4)
    assert pb.memory[RS + RS_XXHI] & 0x20 and not pb.memory[RS + RS_SHADOW] & 0x20, \
        "entering a chimed den must read as found, unclaimed"
    pb.stop(save=False)


def main(frames=None):
    frames = {} if frames is None else frames
    pb = PyBoy(str(ROM), window="null", cgb=True)
    enter_riftwild(pb)
    cairn(pb, frames)
    pb = power_cycle(pb)
    dungeon_trip(pb)
    drowned(pb, frames)
    scar(pb, frames)
    pb.stop(save=False)
    chime(frames)
    print("[riftwild-dens] PASS gated discovery, completion, rewards, "
          "persistence, Compass reveal and exits for all three dens")
    return frames


if __name__ == "__main__":
    main()
