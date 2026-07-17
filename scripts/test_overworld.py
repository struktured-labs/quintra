#!/usr/bin/env python3
"""ROM contract for boss -> authored overworld graph -> next dungeon."""
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

RS, PL, EN, TM, SCREEN = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap", "_loop_current_screen"
))

def put16(pb, p, v):
    pb.memory[p] = v & 255; pb.memory[p + 1] = (v >> 8) & 255

def clear_hostiles(pb):
    for i in range(32):
        p = EN + i * 28
        if pb.memory[p] == 2: pb.memory[p] = pb.memory[p + 1] = 0

def hostile_count(pb):
    return sum(pb.memory[EN + i * 28] == 2 for i in range(32))

def exit_at(pb, x, y, clear=True):
    if clear: clear_hostiles(pb)
    put16(pb, PL + 9, x); put16(pb, PL + 11, y)
    assert pb.memory[PL + 9] == (x & 255) and pb.memory[PL + 11] == (y & 255)
    # A full generated-room swap can straddle several video frames; the
    # outdoor rebuild also streams a complete tilemap before it is safe to
    # inspect authored paths.
    for _ in range(90): pb.tick()

def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()

    # Room zero is divisible by six but is not a defeated boss room.
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 1] == 1 and pb.memory[RS + 17] == 0
    # Restore a neutral generated room before exercising the boss handoff.
    pb.memory[RS + 1] = 0

    # Simulate a cleared first boss and leave through its south door.
    pb.memory[RS + 1] = 6; pb.memory[RS + 11] = 1
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0
    assert pb.memory[RS + 1] == 6, "overworld traversal consumed dungeon depth"
    # Screen 0 is authored E+S only, now bounded by a real tree line rather
    # than dungeon brick. Its reciprocal exits remain door tiles.
    assert pb.memory[TM + 10] == 39 and pb.memory[TM + 9 * 20] == 39
    assert pb.memory[TM + 9 * 20 + 19] == 3 and pb.memory[TM + 16 * 20 + 10] == 3
    assert pb.memory[TM + 8 * 20 + 10] == 36, "Riftwild center lacks path terrain"
    pb.screen.image.save(ROOT / "tmp" / "riftwild-arrival.png")

    # Riftwild encounters never seal exits: leave screen 0 with its generated
    # hostiles alive, then follow graph 0 --E--> 1 --E--> 2 --S--> gate 6.
    assert hostile_count(pb) > 0, "test seed produced no overworld encounter"
    exit_at(pb, 144, 60, clear=False); assert pb.memory[RS + 18] == 1, pb.memory[RS + 18]
    exit_at(pb, 144, 60); assert pb.memory[RS + 18] == 2, pb.memory[RS + 18]
    # Screen 2's cave staircase is a nonlinear hop to vault 15 and back.
    clear_hostiles(pb); put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 15 and pb.memory[RS + 19] == 2
    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 2, "vault staircase did not return"
    exit_at(pb, 72, 120); assert pb.memory[RS + 18] == 6, pb.memory[RS + 18]
    assert pb.memory[TM + 8 * 20 + 10] == 34, "dungeon gate has no portal"
    for _ in range(60): pb.tick()
    pb.screen.image.save(ROOT / "tmp" / "riftwild-gate.png")
    seen = pb.memory[RS + 21] | (pb.memory[RS + 22] << 8)
    expected_seen = sum(1 << cell for cell in (0, 1, 2, 6, 15))
    assert seen == expected_seen, (
        f"Riftwild map did not reveal exact visited cells: {seen:#06x}"
    )
    pb.button("select"); pb.tick(24)
    assert pb.memory[SCREEN] == 8, "SELECT did not open visited Riftwild map"
    # Tile rendering is a deliberate multi-VBlank transaction on real CGB
    # hardware; wait for DISPLAY_ON before judging the composed screen.
    for _ in range(90): pb.tick()
    pb.memory[0xFF4F] = 0
    bg = 0x9800
    assert pb.memory[bg + 6 * 32 + 10] == 33, "current cell lacks tile icon"
    assert pb.memory[bg + 14 * 32 + 14] == 22, "visited vault lacks crystal icon"
    assert pb.memory[bg + 2 * 32 + 14] == 0, "unseen cell was pre-drawn"
    map_shot = ROOT / "tmp" / "riftwild-map.png"
    map_shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(map_shot)
    pb.button("b"); pb.tick(24)
    assert pb.memory[SCREEN] == 5, "map did not resume Riftwild"

    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(8): pb.tick()
    assert pb.memory[RS + 17] == 0, "gate did not return to dungeon mode"
    assert pb.memory[RS + 1] == 7, "next dungeon did not advance depth"
    assert pb.memory[RS + 20] == 1, "new dungeon map did not reset to entry cell"
    pb.stop(save=False)
    print("[overworld] PASS boss exit -> visited 4x4 map -> dungeon gate")

if __name__ == "__main__": main()
