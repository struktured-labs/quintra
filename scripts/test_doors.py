#!/usr/bin/env python3
"""ROM regression: every cardinal boundary door is geometrically usable."""
import re
from pathlib import Path
from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m: raise RuntimeError(name)
    return int(m.group(1), 16)

RS, PL, EN, TM, SEALED = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed"))

def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF

def crosses(x, y, synthetic_door=None):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    if synthetic_door is not None:
        tx, ty = synthetic_door
        pb.memory[TM + ty * 20 + tx] = 3
        # Secret doors are always two tiles wide along their wall.
        if ty in (0, 17):
            pb.memory[TM + ty * 20 + tx + 1] = 3
        else:
            pb.memory[TM + (ty + 1) * 20 + tx] = 3
    put16(pb, PL + 9, x); put16(pb, PL + 11, y)
    for _ in range(8): pb.tick()
    result = pb.memory[RS + 1]
    pb.stop(save=False)
    return result == 1

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
    pb.memory[TM + 9] = pb.memory[TM + 10] = 3
    pb.memory[RS + 6] = 0
    pb.memory[SEALED] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 0)
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

def main():
    positions = {
        "north": (72, 0, None), "east": (144, 60, None),
        "south": (72, 120, None), "west": (0, 60, None),
        # A shot-open secret can occur away from the centered main doors.
        # This exact geometry previously let the hero walk to signed y=-8
        # without transitioning, softlocking an otherwise cleared room.
        "off-center-secret": (36, 0, (5, 0)),
    }
    failed = [name for name, args in positions.items() if not crosses(*args)]
    if not locked_north_holds(): failed.append("locked-north-boundary")
    if not open_room_with_hostile_allows_exit(): failed.append("open-combat-exit")
    if not blocked_crate_north_face_holds(): failed.append("blocked-crate-north-face")
    if failed: raise SystemExit(f"[doors] FAIL unreachable: {', '.join(failed)}")
    print("[doors] PASS cardinal/secret traversal + selective seals + crate boundaries")

if __name__ == "__main__": main()
