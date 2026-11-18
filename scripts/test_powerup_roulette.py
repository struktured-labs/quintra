#!/usr/bin/env python3
"""ROM contract: Penta Dragon-style roulette capsule (cycle + lock face).

Spec §3 / Carbon: 8 frames/face Normal, lock = face shown on overlap.
Set QUINTRA_POWERUP_GIF_DIR for a 4x preview GIF.
"""
import os
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
GIF_DIR = os.environ.get("QUINTRA_POWERUP_GIF_DIR")

ENT_PICKUP = 3
PICKUP_ROULETTE = 28
X, Y = 9, 11


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def boot_class(class_id, screen, player):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    for _ in range(class_id):
        pb.button("down")
        for _ in range(16):
            pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id
    return pb


class Frames:
    def __init__(self):
        self.frames = []

    def grab(self, pb, every=1, n=1):
        for i in range(n):
            pb.tick()
            if GIF_DIR and i % every == 0:
                self.frames.append(pb.screen.image.copy().convert("RGB")
                                   .resize((640, 576), 0))

    def save(self, name):
        if not GIF_DIR or not self.frames:
            return
        Path(GIF_DIR).mkdir(parents=True, exist_ok=True)
        self.frames[0].save(Path(GIF_DIR) / name, save_all=True,
                            append_images=self.frames[1:], duration=50, loop=0)
        self.frames = []


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pu_id, pu_ticks, test_cmd = map(
        addr, ("_powerup_id", "_powerup_ticks", "_powerup_test_cmd"))
    gif = Frames()
    pb = boot_class(1, screen, player)
    for _ in range(2):
        for i in range(32 * 28):
            pb.memory[entities + i] = 0
        pb.tick()

    # Stand still, spawn a roulette beside the hero via the test hook.
    pb.memory[addr("_powerup_world_live")] = 1
    pb.memory[test_cmd] = 1
    gif.grab(pb, n=4)
    slot = None
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == ENT_PICKUP and pb.memory[e + 17] == PICKUP_ROULETTE:
            slot = e
            break
    assert slot, "test hook did not spawn a roulette capsule"
    face0 = pb.memory[slot + 18]
    tile0 = pb.memory[slot + 12]
    # 8 frames/face on Normal: after 8 ticks the face must have advanced.
    gif.grab(pb, n=8)
    face1 = pb.memory[slot + 18]
    tile1 = pb.memory[slot + 12]
    assert face1 != face0 or tile1 != tile0, (
        f"roulette did not cycle in 8 frames (face {face0}->{face1})")
    # Keep cycling a bit so the GIF reads as a fast rotate.
    gif.grab(pb, every=1, n=24)
    latched = pb.memory[slot + 19]  # ai_data[2], the visible face
    # Move the capsule onto the player so overlap locks that face.
    px = pb.memory[player + X] | (pb.memory[player + X + 1] << 8)
    py = pb.memory[player + Y] | (pb.memory[player + Y + 1] << 8)
    raw = (px + 4) << 8
    for i in range(4):
        pb.memory[slot + 2 + i] = (raw >> (i * 8)) & 0xFF
    raw = (py + 4) << 8
    for i in range(4):
        pb.memory[slot + 6 + i] = (raw >> (i * 8)) & 0xFF
    gif.grab(pb, n=24)  # lock freeze is 20 frames, then collect
    assert pb.memory[pu_id] == latched, (
        f"lock awarded {pb.memory[pu_id]}, visible face was {latched}")
    assert pb.memory[pu_ticks] > 0, "roulette collect started no timer"
    gif.grab(pb, every=2, n=30)
    gif.save("roulette.gif")
    pb.stop(save=False)
    print("[powerup-roulette] PASS cycle 8f/face and lock=visible face")


if __name__ == "__main__":
    main()
