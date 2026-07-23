#!/usr/bin/env python3
"""ROM regression: every cardinal boundary door is geometrically usable."""
import re
from pathlib import Path
from pyboy import PyBoy
from quintra_topology import STAGE_START, dungeon_neighbor

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m: raise RuntimeError(name)
    return int(m.group(1), 16)

RS, PL, EN, TM, SEALED, SHADOW_OAM = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_shadow_OAM"))

def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF

def read16(pb, address):
    return pb.memory[address] | (pb.memory[address + 1] << 8)

def player_oam_matches(pb):
    """Return whether all four player metasprite tiles match player state."""
    px, py = read16(pb, PL + 9), read16(pb, PL + 11)
    expected = ((py + 16, px + 8), (py + 16, px + 16),
                (py + 24, px + 8), (py + 24, px + 16))
    # GBDK writes sprite positions through shadow OAM during VBlank. This is
    # the authoritative game-side buffer (and stable across PyBoy backends),
    # whereas hardware OAM can be momentarily inaccessible during a PPU tick.
    actual = tuple((pb.memory[SHADOW_OAM + i * 4],
                    pb.memory[SHADOW_OAM + i * 4 + 1]) for i in range(4))
    return actual == expected and all(y and x for y, x in actual)

def assert_player_oam_visible(pb, label):
    """The post-slide hero must be on-screen, not merely OBJ-enabled."""
    px, py = read16(pb, PL + 9), read16(pb, PL + 11)
    expected = ((py + 16, px + 8), (py + 16, px + 16),
                (py + 24, px + 8), (py + 24, px + 16))
    actual = tuple((pb.memory[SHADOW_OAM + i * 4],
                    pb.memory[SHADOW_OAM + i * 4 + 1]) for i in range(4))
    assert player_oam_matches(pb), (
        f"{label}: hero OAM vanished after transition: "
        f"player={px},{py} actual={actual} expected={expected}")

EDGE_POSITION = {
    0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60),
}
EDGE_TILES = {
    0: ((9, 0), (10, 0)),
    1: ((19, 8), (19, 9)),
    2: ((9, 16), (10, 16)),
    3: ((0, 8), (0, 9)),
}


def crosses(direction, off_center=False):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    # Let the initial room's staged palette/OAM transaction settle before
    # injecting a boundary position. Otherwise this fixture can overlap the
    # initial entry reveal with the new slide and falsely inspect its old OAM.
    for _ in range(240): pb.tick()
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    # Exercise one guaranteed snake-spine edge in each direction. Seeded maze
    # seams deliberately mean no single 6x5 cell owns four exits every run.
    stage, size = 2, 22
    cell = {0: 6, 1: 0, 2: 5, 3: 1}[direction]
    pb.memory[RS + 11] = stage
    pb.memory[RS + 1] = STAGE_START[stage] + cell
    pb.memory[RS + 6] = 0xFF
    for tx, ty in EDGE_TILES[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    x, y = EDGE_POSITION[direction]
    if off_center:
        assert direction == 0
        x = 36
        pb.memory[TM + 5] = pb.memory[TM + 6] = 3
    put16(pb, PL + 9, x); put16(pb, PL + 11, y)
    target = dungeon_neighbor(cell, size, direction)
    target_room = STAGE_START[stage] + target
    # A full cardinal slide streams its tilemap across many VBlanks. At least
    # one sampled beat must show the reconstructed hero while arrival safety
    # remains active; this directly catches "invulnerable but invisible".
    visible_during_arrival = False
    for _ in range(120):
        pb.tick()
        # This suite owns transition geometry, not encounter survival. Clear
        # the freshly generated destination hostiles before their knockback
        # can throw an idle fixture back through its arrival threshold.
        if pb.memory[RS + 1] == target_room:
            for i in range(32):
                entity = EN + i * 28
                if pb.memory[entity] == 2:
                    pb.memory[entity] = pb.memory[entity + 1] = 0
        if pb.memory[PL + 15] > 0 and player_oam_matches(pb):
            visible_during_arrival = True
    result = pb.memory[RS + 1]
    # Bit 1 of LCDC is the OBJ/sprite-enable bit. Sliding room transitions
    # intentionally hide sprites while streaming tilemaps, then must restore
    # them before gameplay resumes or the hero appears to vanish.
    sprites_visible = (pb.memory[0xFF40] & 0x02) != 0
    assert visible_during_arrival, "arrival invulnerability hid the hero"
    assert_player_oam_visible(pb, f"door {x},{y}")
    pb.stop(save=False)
    return result == STAGE_START[stage] + target and sprites_visible

def locked_north_holds():
    """A live hostile must not let repeated north input escape to signed y=-8."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    for i in range(32 * 28): pb.memory[EN + i] = 0
    enemy = EN
    pb.memory[enemy] = 2
    pb.memory[enemy + 1] = 3
    pb.memory[enemy + 3] = 104
    pb.memory[enemy + 7] = 72
    pb.memory[enemy + 14] = 8
    pb.memory[enemy + 17] = 0
    pb.memory[enemy + 25] = 0x88
    pb.memory[TM + 9] = pb.memory[TM + 10] = 3
    pb.memory[SEALED] = 1
    pb.memory[RS + 6] = 0  # north is a gated forward exit, not the return door
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 0)
    pb.button_press("up")
    for _ in range(30): pb.tick()
    pb.button_release("up")
    y = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    room = pb.memory[RS + 1]
    pb.stop(save=False)
    return room == 0 and y == 0

def open_room_with_hostile_allows_exit():
    """A non-seal combat room remains fleeable even with a live hostile."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    for i in range(32 * 28): pb.memory[EN + i] = 0
    pb.memory[EN] = 2
    pb.memory[EN + 1] = 3
    pb.memory[EN + 3] = 104
    pb.memory[EN + 7] = 72
    pb.memory[EN + 14] = 8
    pb.memory[EN + 25] = 0x88
    pb.memory[TM + 8 * 20 + 19] = pb.memory[TM + 9 * 20 + 19] = 3
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    put16(pb, PL + 9, 144)
    put16(pb, PL + 11, 60)
    for _ in range(8): pb.tick()
    room = pb.memory[RS + 1]
    pb.stop(save=False)
    return room == 1

def blocked_crate_north_face_holds():
    """Walking upward cannot hide the hero's head under a stationary crate."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    for i in range(32 * 28): pb.memory[EN + i] = 0
    # A 2x2 crate at pixels 72,64 with walls immediately north so it cannot
    # slide. The visible 16px hero must stop at y=80, not overlap to y=72.
    for x in (9, 10): pb.memory[TM + 7 * 20 + x] = 2
    pb.memory[TM + 8 * 20 + 9] = 25
    pb.memory[TM + 8 * 20 + 10] = 28
    pb.memory[TM + 9 * 20 + 9] = 29
    pb.memory[TM + 9 * 20 + 10] = 30
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 96)
    pb.button_press("up")
    for _ in range(90): pb.tick()
    pb.button_release("up")
    y = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    intact = tuple(pb.memory[TM + y0 * 20 + x0]
                   for y0 in (8, 9) for x0 in (9, 10)) == (25, 28, 29, 30)
    pb.stop(save=False)
    return y == 80 and intact

def pressure_plate_reveals_secret():
    """Only a cairn—not the hero—holds a plate and opens its side passage."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    for i in range(32 * 28): pb.memory[EN + i] = 0
    # This is the authored puzzle coordinate family in procgen: x=7 or 12.
    # x=7 creates north-wall doors at 7/8, safely beside the main 9/10 door.
    sx, sy = 7, 5
    pb.memory[TM + sy * 20 + sx] = 33  # BGT_SWITCH
    pb.memory[TM + sx] = 2             # BGT_WALL, before the reveal
    pb.memory[TM + sx + 1] = 2
    # Standing on the plate is deliberate negative evidence: the landscape
    # weight puzzle must not collapse into a walk-over button.
    put16(pb, PL + 9, sx * 8 - 8)
    put16(pb, PL + 11, sy * 8 - 12)
    for _ in range(8): pb.tick()
    hero_did_not_solve = (pb.memory[TM + sx] == 2
                          and pb.memory[TM + sy * 20 + sx] == 33)

    # Stamp a 2x2 cairn immediately west, stand behind it, and hold right.
    bx = sx - 2
    # Generated rooms may put unrelated walls around this synthetic fixture.
    # Give the hero, cairn, and its one-tile destination a known walkable lane.
    for y in range(sy - 1, sy + 3):
        for x in range(bx - 2, sx + 2):
            pb.memory[TM + y * 20 + x] = 1
    pb.memory[TM + sy * 20 + sx] = 33
    pb.memory[TM + sy * 20 + bx] = 25
    pb.memory[TM + sy * 20 + bx + 1] = 28
    pb.memory[TM + (sy + 1) * 20 + bx] = 29
    pb.memory[TM + (sy + 1) * 20 + bx + 1] = 30
    pb.memory[TM + (sy + 1) * 20 + sx] = 1
    put16(pb, PL + 9, bx * 8 - 16)
    put16(pb, PL + 11, sy * 8 - 8)
    pb.button_press("right")
    for _ in range(90):
        pb.tick()
        if pb.memory[TM + sx] == 3:
            break
    pb.button_release("right")
    opened = (pb.memory[TM + sx] == 3 and pb.memory[TM + sx + 1] == 3)
    cairn_holds = pb.memory[TM + sy * 20 + sx] in (25, 28, 29, 30)
    tiles = (pb.memory[TM + sx], pb.memory[TM + sx + 1],
             pb.memory[TM + sy * 20 + sx])
    player_xy = (pb.memory[PL + 9] | (pb.memory[PL + 10] << 8),
                 pb.memory[PL + 11] | (pb.memory[PL + 12] << 8))
    # Enter the newly opened cache. A cache is now an overlay on this graph
    # cell, then its only legal return restores the same stable room number.
    parent_room = pb.memory[RS + 1]
    put16(pb, PL + 9, sx * 8 - 4)
    put16(pb, PL + 11, 0)
    for _ in range(180):
        pb.tick()
        if pb.memory[RS + 13] == 2:
            break
    entered_cache = pb.memory[RS + 13] == 2 and pb.memory[RS + 1] == parent_room
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 120)
    for _ in range(180):
        pb.tick()
        if pb.memory[RS + 13] == 0:
            break
    returned_to_parent = pb.memory[RS + 13] == 0 and pb.memory[RS + 1] == parent_room
    if not (hero_did_not_solve and opened and cairn_holds):
        pb.stop(save=False)
        raise AssertionError(f"plate did not reveal secret: north/switch={tiles} player={player_xy}")
    if not (entered_cache and returned_to_parent):
        details = (pb.memory[RS + 1], pb.memory[RS + 13])
        pb.stop(save=False)
        raise AssertionError(
            "pressure-plate cache traversal failed: "
            f"entered={entered_cache} returned={returned_to_parent} "
            f"parent={parent_room} room={details[0]} secret={details[1]}")
    pb.stop(save=False)
    return (hero_did_not_solve and opened and cairn_holds
            and entered_cache and returned_to_parent)

def main():
    positions = {
        "north": (0, False), "east": (1, False),
        "south": (2, False), "west": (3, False),
        # A shot-open secret can occur away from the centered main doors.
        # This exact geometry previously let the hero walk to signed y=-8
        # without transitioning, softlocking an otherwise cleared room.
        "off-center-door": (0, True),
    }
    failed = [name for name, args in positions.items() if not crosses(*args)]
    if not locked_north_holds(): failed.append("locked-north-boundary")
    if not open_room_with_hostile_allows_exit(): failed.append("open-combat-exit")
    if not blocked_crate_north_face_holds(): failed.append("blocked-crate-north-face")
    if not pressure_plate_reveals_secret(): failed.append("pressure-plate-secret")
    if failed: raise SystemExit(f"[doors] FAIL unreachable or sprites hidden: {', '.join(failed)}")
    print("[doors] PASS cardinal/secret traversal + visible sprite layer + selective seals + crate boundaries")

if __name__ == "__main__": main()
