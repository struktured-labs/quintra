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

RS, PL, EN = addr("_run_state"), addr("_player"), addr("_entities")

def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF

def crosses(x, y):
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
    put16(pb, PL + 9, x); put16(pb, PL + 11, y)
    for _ in range(8): pb.tick()
    result = pb.memory[RS + 1]
    pb.stop(save=False)
    return result == 1

def main():
    positions = {"north": (72, 0), "east": (144, 60),
                 "south": (72, 120), "west": (0, 60)}
    failed = [name for name, pos in positions.items() if not crosses(*pos)]
    if failed: raise SystemExit(f"[doors] FAIL unreachable: {', '.join(failed)}")
    print("[doors] PASS north/east/south/west")

if __name__ == "__main__": main()
