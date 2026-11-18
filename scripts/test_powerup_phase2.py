#!/usr/bin/env python3
"""ROM contract: Phase 2-4 power-ups (Formation, Halo, Long Reach, Blast, Wingmates).

Spec: docs/superpowers/specs/2026-11-16-temporary-powerups.md.
Set QUINTRA_POWERUP_GIF_DIR to write 4x preview GIFs.
"""
import os
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
GIF_DIR = os.environ.get("QUINTRA_POWERUP_GIF_DIR")

FORMATION, HALO, LONGREACH, BLAST, WINGMATES = 4, 5, 6, 7, 8
ENT_PROJECTILE, ENT_PICKUP, ENT_FX = 1, 3, 4
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
PROJ_FLAG_SPLASH, PROJ_FLAG_PU_COPY = 0x08, 0x80
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
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id, (
        f"could not enter live class-{class_id} room")
    return pb


def clear_entities(pb, entities):
    for _ in range(2):
        for i in range(32 * 28):
            pb.memory[entities + i] = 0
        pb.tick()


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


def shot_info(pb, entities):
    out = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] != ENT_PROJECTILE or not (pb.memory[e + 1] & EF_ACTIVE):
            continue
        if not (pb.memory[e + 1] & EF_PLAYER_PROJ):
            continue
        out.append((i, pb.memory[e + 20], pb.memory[e + 25], pb.memory[e + 16]))
    return out


def fire_once(pb, frames, hold=5):
    """Primary fire needs a facing (spawn rejects dx=dy=0). Snapshot early:
    Sauran Formation copies only live ~14 frames after the -8 ttl trim.
    """
    pb.button("right", True)
    pb.button("a", True)
    frames.grab(pb, n=hold)
    pb.button("a", False)
    pb.button("right", False)


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pu_id, pu_ticks = map(addr, ("_powerup_id", "_powerup_ticks"))
    gif = Frames()

    # Sauran (class 1): a spear is a clean projectile to count copies on.
    pb = boot_class(1, screen, player)
    clear_entities(pb, entities)

    # ---- FORMATION: primary + two copies ----
    pb.memory[pu_id] = FORMATION
    pb.memory[pu_ticks] = 90
    for _ in range(4):
        pb.tick()
    fire_once(pb, gif, hold=5)
    shots_info = shot_info(pb, entities)
    copies = sum(1 for _, ai3, *_ in shots_info if ai3 & PROJ_FLAG_PU_COPY)
    assert len(shots_info) >= 3, f"Formation did not spawn copies: {shots_info}"
    assert copies >= 2, f"Formation copies missing PU_COPY: {shots_info}"
    gif.grab(pb, every=2, n=40)
    gif.save("formation.gif")

    # ---- HALO: every 3rd shot grows an 8-way ring ----
    # fire_count is static and already includes Formation, so look after
    # every shot instead of only at the end (ring ttl is 20 frames).
    clear_entities(pb, entities)
    pb.memory[pu_id] = HALO
    pb.memory[pu_ticks] = 75
    for _ in range(2):
        pb.tick()
    best = []
    for n in range(3):
        fire_once(pb, gif, hold=5)
        shots_info = shot_info(pb, entities)
        if len(shots_info) > len(best):
            best = shots_info
        for _ in range(12):
            pb.tick()
        clear_entities(pb, entities)
        pb.memory[pu_id] = HALO
        pb.memory[pu_ticks] = 75
    copies = sum(1 for _, ai3, *_ in best if ai3 & PROJ_FLAG_PU_COPY)
    assert copies >= 4, f"Halo ring too small: {best} (best copies {copies})"
    gif.grab(pb, every=2, n=20)
    gif.save("halo.gif")

    # ---- LONG REACH: hitbox nibbles doubled, travel +50% ----
    clear_entities(pb, entities)
    pb.memory[pu_id] = 0
    pb.memory[pu_ticks] = 0
    for _ in range(4):
        pb.tick()
    fire_once(pb, gif, hold=4)
    base = None
    shots_info = shot_info(pb, entities)
    if shots_info:
        i = shots_info[0][0]
        e = entities + i * 28
        base = (pb.memory[e + 25], pb.memory[e + 16])
    assert base, "no baseline spear to compare Long Reach against"
    # Wait out the primary fire cooldown so the Long Reach shot can spawn.
    for _ in range(24):
        pb.tick()
    clear_entities(pb, entities)
    pb.memory[pu_id] = LONGREACH
    pb.memory[pu_ticks] = 75
    for _ in range(4):
        pb.tick()
    fire_once(pb, gif, hold=4)
    got = None
    shots_info = shot_info(pb, entities)
    if shots_info:
        i = shots_info[0][0]
        e = entities + i * 28
        got = (pb.memory[e + 25], pb.memory[e + 16])
    assert got, "Long Reach fired no spear"
    bw, bh = (base[0] >> 4) & 0xF, base[0] & 0xF
    gw, gh = (got[0] >> 4) & 0xF, got[0] & 0xF
    assert gw >= min(0xF, bw * 2) or gh >= min(0xF, bh * 2) or got[1] > base[1], (
        f"Long Reach did not grow hitbox/ttl: base={base} got={got}")
    gif.grab(pb, every=2, n=40)
    gif.save("longreach.gif")

    # ---- BLAST ASSIST: primary is marked to bloom ----
    clear_entities(pb, entities)
    pb.memory[pu_id] = BLAST
    pb.memory[pu_ticks] = 90
    for _ in range(4):
        pb.tick()
    fire_once(pb, gif, hold=5)
    marked = sum(1 for _, ai3, *_ in shot_info(pb, entities) if ai3 & PROJ_FLAG_SPLASH)
    assert marked >= 1, "Blast Assist did not mark a shot with SPLASH"
    gif.grab(pb, every=2, n=40)
    gif.save("blast.gif")

    # ---- WINGMATES: two flank FX buddies ----
    clear_entities(pb, entities)
    pb.memory[pu_id] = 0
    pb.memory[pu_ticks] = 0
    # Collect via a poked Capsule so helpers_on_collect runs.
    px = pb.memory[player + X] | (pb.memory[player + X + 1] << 8)
    py = pb.memory[player + Y] | (pb.memory[player + Y + 1] << 8)
    e = entities
    pb.memory[e] = ENT_PICKUP
    pb.memory[e + 1] = 0x03
    raw = (px + 4) << 8
    for i in range(4):
        pb.memory[e + 2 + i] = (raw >> (i * 8)) & 0xFF
    raw = (py + 8) << 8
    for i in range(4):
        pb.memory[e + 6 + i] = (raw >> (i * 8)) & 0xFF
    pb.memory[e + 16] = 255
    pb.memory[e + 17] = 27  # PICKUP_POWERUP
    pb.memory[e + 18] = WINGMATES
    pb.memory[e + 25] = 0x88
    gif.grab(pb, n=8)
    assert pb.memory[pu_id] == WINGMATES, "Wingmates capsule not collected"
    buddies = [i for i in range(32) if pb.memory[entities + i * 28] == ENT_FX
               and (pb.memory[entities + i * 28 + 1] & EF_ACTIVE)]
    assert len(buddies) >= 2, f"Wingmates did not spawn two buddies: {buddies}"
    fire_once(pb, gif, hold=5)
    gif.grab(pb, every=2, n=40)
    gif.save("wingmates.gif")

    pb.stop(save=False)
    print("[powerup-phase2] PASS Formation/Halo/LongReach/Blast/Wingmates")


if __name__ == "__main__":
    main()
