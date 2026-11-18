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


def player_shots(pb, entities):
    out = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == ENT_PROJECTILE and (pb.memory[e + 1] & EF_ACTIVE):
            if pb.memory[e + 1] & EF_PLAYER_PROJ:
                out.append(i)
    return out


def fire_a(pb, frames, n=12):
    pb.button("a")
    frames.grab(pb, n=n)


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
    fire_a(pb, gif, n=16)
    shots = player_shots(pb, entities)
    copies = 0
    for i in shots:
        flags = pb.memory[entities + i * 28 + 17 + 3]  # ai_data[3] at +20?
        # entity: type, flags, x_frac, x(2), x_pad, y_frac, y(2), y_pad, vx, vy,
        # sprite, pal, hp, state, state_timer, ai_data[8], hitbox, damage, oam
        # offsets: 0 type, 1 flags, 2 x_frac, 3-4 x, 5 x_pad, 6 y_frac, 7-8 y,
        # 9 y_pad, 10 vx, 11 vy, 12 tile, 13 pal, 14 hp, 15 state, 16 timer,
        # 17..24 ai_data, 25 hitbox, 26 damage, 27 oam
    # recompute properly
    shots_info = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] != ENT_PROJECTILE or not (pb.memory[e + 1] & EF_ACTIVE):
            continue
        if not (pb.memory[e + 1] & EF_PLAYER_PROJ):
            continue
        ai3 = pb.memory[e + 17 + 3]
        shots_info.append((i, ai3))
    copies = sum(1 for _, ai3 in shots_info if ai3 & PROJ_FLAG_PU_COPY)
    assert len(shots_info) >= 3, f"Formation did not spawn copies: {shots_info}"
    assert copies >= 2, f"Formation copies missing PU_COPY: {shots_info}"
    gif.grab(pb, every=2, n=40)
    gif.save("formation.gif")

    # ---- HALO: every 3rd shot grows an 8-way ring ----
    clear_entities(pb, entities)
    pb.memory[pu_id] = HALO
    pb.memory[pu_ticks] = 75
    for _ in range(2):
        pb.tick()
    for n in range(3):
        fire_a(pb, gif, n=20)
        for _ in range(8):
            pb.button("a", False)
            pb.tick()
    shots_info = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] != ENT_PROJECTILE or not (pb.memory[e + 1] & EF_ACTIVE):
            continue
        if not (pb.memory[e + 1] & EF_PLAYER_PROJ):
            continue
        shots_info.append((i, pb.memory[e + 20]))
    copies = sum(1 for _, ai3 in shots_info if ai3 & PROJ_FLAG_PU_COPY)
    assert copies >= 4, f"Halo ring too small: {len(shots_info)} shots, {copies} copies"
    gif.grab(pb, every=2, n=30)
    gif.save("halo.gif")

    # ---- LONG REACH: hitbox nibbles doubled, travel +50% ----
    clear_entities(pb, entities)
    pb.memory[pu_id] = 0
    pb.memory[pu_ticks] = 0
    for _ in range(4):
        pb.tick()
    fire_a(pb, gif, n=4)
    base = None
    for i in range(32):
        e = entities + i * 28
        if (pb.memory[e] == ENT_PROJECTILE and (pb.memory[e + 1] & EF_PLAYER_PROJ)
                and (pb.memory[e + 1] & EF_ACTIVE)):
            base = (pb.memory[e + 25], pb.memory[e + 16])
            break
    assert base, "no baseline spear to compare Long Reach against"
    clear_entities(pb, entities)
    pb.memory[pu_id] = LONGREACH
    pb.memory[pu_ticks] = 75
    for _ in range(4):
        pb.tick()
    fire_a(pb, gif, n=4)
    got = None
    for i in range(32):
        e = entities + i * 28
        if (pb.memory[e] == ENT_PROJECTILE and (pb.memory[e + 1] & EF_PLAYER_PROJ)
                and (pb.memory[e + 1] & EF_ACTIVE)):
            got = (pb.memory[e + 25], pb.memory[e + 16])
            break
    assert got, "Long Reach fired no spear"
    # hitbox nibbles should have grown (unless already 0xF)
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
    fire_a(pb, gif, n=8)
    marked = 0
    for i in range(32):
        e = entities + i * 28
        if (pb.memory[e] == ENT_PROJECTILE and (pb.memory[e + 1] & EF_ACTIVE)
                and (pb.memory[e + 1] & EF_PLAYER_PROJ)
                and (pb.memory[e + 20] & PROJ_FLAG_SPLASH)):
            marked += 1
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
    fire_a(pb, gif, n=16)
    gif.grab(pb, every=2, n=40)
    gif.save("wingmates.gif")

    pb.stop(save=False)
    print("[powerup-phase2] PASS Formation/Halo/LongReach/Blast/Wingmates")


if __name__ == "__main__":
    main()
