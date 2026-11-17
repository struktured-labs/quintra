#!/usr/bin/env python3
"""Picsean's full-Will Tide Vortex spirals out and sweeps the whole room.

Spec: docs/superpowers/specs/2026-11-15-picsean-tide-vortex.md

Checks: the front grows from the cast point to past the farthest corner,
every body around it (front, back, sides, corners) is hit in distance order,
hostile shots are washed out, a heavy body takes capped damage and at most
two hits, the arm art is in OAM, the eye stays put after Picsean swims
away, and it all cleans up. A crowded fixture compares logic updates
during the vortex against the same room idle.

Set QUINTRA_VORTEX_GIF=<path> to also record a GIF of a real room.
"""
import os
import re
from pathlib import Path

from test_will_max import (
    ENTITIES, ENTITY_SIZE, LEVEL_OFFSET, PLAYER, WILL_OFFSET,
    boot, clear_arena, player_shots, put16,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


TICKS = addr("_picsean_vortex_ticks")
RADIUS = addr("_picsean_vortex_radius")
CLOCK = addr("_entity_anim_counter")
COUNT = addr("_entity_enemy_count")
STATUS_KIND = addr("_enemy_status_kind")
STATUS_TICKS = addr("_enemy_status_ticks")
OAM = 0xFE00
VORTEX_TILES = range(200, 204)
QSTATUS_STOP = 4
EF_ELITE = 0x20
HP, IFRAMES, SHIELD, LCK = PLAYER + 2, PLAYER + 15, PLAYER + 20, PLAYER + 8
PX, PY = 72, 60          # hero centre is (80, 68)
HEAVY_CAP = 6


def put_fix8(pb, address, pixels):
    raw = (pixels & 0xFFFF) << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def make_crawler(pb, slot, x, y, hp=200, flags=0x07, stop=True):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 2
    pb.memory[e + 1] = flags
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = 20
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 120
    pb.memory[e + 17] = 0            # blue crawler
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    if stop:
        pb.memory[STATUS_KIND + slot] = QSTATUS_STOP
        pb.memory[STATUS_TICKS + slot] = 250
    return e


def make_shot(pb, slot, x, y):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x03
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = 28
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 250          # long-lived, stationary
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    return e


def arm(pb):
    pb.tick(30)
    clear_arena(pb)
    put16(pb, PLAYER + 9, PX)
    put16(pb, PLAYER + 11, PY)
    pb.memory[PLAYER + 13] = 1
    pb.memory[HP] = pb.memory[PLAYER + 1]
    pb.memory[IFRAMES] = pb.memory[SHIELD] = 0
    pb.memory[LCK] = 0               # no crit doubling: exact cap check
    pb.memory[PLAYER + WILL_OFFSET] = 90
    pb.memory[PLAYER + LEVEL_OFFSET] = 1
    # Fixture recasts should not wait out the 360-frame play lock.
    pb.memory[addr("_picsean_vortex_slow_charge")] = 0


def fire_max(pb):
    pb.button_press("right")
    pb.button_press("a")
    for _ in range(40):
        pb.tick()
        if pb.memory[PLAYER + LEVEL_OFFSET] == 0:
            break
    pb.button_release("a")
    pb.button_release("right")
    assert pb.memory[PLAYER + WILL_OFFSET] < 8, "MAX did not fire"


def check(label, cond, detail=""):
    assert cond, f"{label} FAILED {detail}"
    print(f"  ok  {label}")


def vortex_oam(pb):
    return [k for k in range(24, 36)
            if pb.memory[OAM + k * 4] and pb.memory[OAM + k * 4 + 2] in VORTEX_TILES]


def contract(pb):
    arm(pb)
    # Bodies on every side, near to far. Corners of the 160x136 room.
    spots = {
        "east-near": (96, 64), "west-near": (52, 64), "north": (76, 28),
        "south": (76, 104), "nw-corner": (10, 10), "ne-corner": (140, 10),
        "sw-corner": (10, 116), "se-corner": (140, 116),
    }
    bodies = {name: make_crawler(pb, 10 + i, x, y)
              for i, (name, (x, y)) in enumerate(spots.items())}
    elite = make_crawler(pb, 20, 120, 64, flags=0x07 | EF_ELITE)
    shots = [make_shot(pb, 22, 30, 40), make_shot(pb, 23, 130, 96)]
    pb.memory[COUNT] = len(bodies) + 1
    hp0 = {n: pb.memory[e + 14] for n, e in bodies.items()}
    elite_hp = [pb.memory[elite + 14]]
    fire_max(pb)
    check("vortex: active after the MAX", pb.memory[TICKS] > 0,
          f"ticks={pb.memory[TICKS]}")
    first_hit, radii, arm_frames = {}, [], 0
    hits = {n: 0 for n in bodies}
    last_hp = dict(hp0)
    tiles_seen = set()
    for frame in range(220):
        pb.tick()
        if pb.memory[TICKS]:
            radii.append(pb.memory[RADIUS])
        oam = vortex_oam(pb)
        if oam:
            arm_frames += 1
            tiles_seen |= {pb.memory[OAM + k * 4 + 2] for k in oam}
        for n, e in bodies.items():
            hp = pb.memory[e + 14]
            if hp < last_hp[n]:
                hits[n] += 1
                first_hit.setdefault(n, frame)
            last_hp[n] = hp
        if pb.memory[elite + 14] != elite_hp[-1]:
            elite_hp.append(pb.memory[elite + 14])
        if not pb.memory[TICKS] and frame > 10:
            break
    check("front grows monotonically",
          all(b >= a for a, b in zip(radii, radii[1:])) and radii[-1] > radii[0],
          f"radii={radii[:3]}..{radii[-3:]}")
    check("front spans the room (past the far corner)", max(radii) >= 100,
          f"max r={max(radii)}")
    check("every body on every side was hit", len(first_hit) == len(bodies),
          f"missed={set(bodies) - set(first_hit)}")
    near = max(first_hit[n] for n in ("east-near", "west-near"))
    far = min(first_hit[n] for n in spots if n.endswith("corner"))
    check("sweep order: near bodies before corners", near < far,
          f"near={near} far={far}")
    check("strong hits: each body lost at least MAX+4",
          all(hp0[n] - pb.memory[e + 14] >= 5 for n, e in bodies.items()),
          f"hp={ {n: pb.memory[e + 14] for n, e in bodies.items()} }")
    check("arms sweep a second hit through most bodies",
          sum(h == 2 for h in hits.values()) >= 6
          and all(h <= 2 for h in hits.values()), f"hits={hits}")
    elite_hits = len(elite_hp) - 1
    elite_loss = elite_hp[0] - elite_hp[-1]
    check("heavy body: at most two capped hits",
          1 <= elite_hits <= 2 and elite_loss <= 2 * HEAVY_CAP + 2,
          f"hits={elite_hits} loss={elite_loss}")
    check("hostile shots washed out",
          all(not (pb.memory[s] == 1 and pb.memory[s + 1] & 1
                   and not pb.memory[s + 1] & 0x10) for s in shots))
    check("arm art drawn in OAM 24..35 with several cels",
          arm_frames >= 40 and len(tiles_seen) >= 3,
          f"frames={arm_frames} tiles={sorted(tiles_seen)}")
    # A busy room's logic update can straddle a frame: let the last
    # vortex tick (counter at 0, then cleanup) finish before checking.
    pb.tick(4)
    check("cleanup: vortex idle, OAM 24..35 free, no carrier",
          pb.memory[TICKS] == 0 and not vortex_oam(pb)
          and not [s for s in player_shots(pb) if pb.memory[s + 23] == 0xF0],
          f"ticks={pb.memory[TICKS]} oam={vortex_oam(pb)} "
          f"carriers={[s for s in player_shots(pb) if pb.memory[s + 23] == 0xF0]}")
    check("no i-frames granted", pb.memory[IFRAMES] == 0,
          f"iframes={pb.memory[IFRAMES]}")


def anchored(pb):
    """The spiral stays at the tile where Will was spent.

    After the MAX fires, Picsean is teleported on top of a far body.
    If the eye followed her, that body would be hit immediately (it
    sits in the new 10px core). An anchored eye hits the body next to
    the original cast point first, and the far body only once the
    front has grown across the room.
    """
    arm(pb)
    near = make_crawler(pb, 10, 96, 64)
    far = make_crawler(pb, 11, 16, 16)
    pb.memory[COUNT] = 2
    near_hp0 = pb.memory[near + 14]
    far_hp0 = pb.memory[far + 14]
    fire_max(pb)
    check("anchor: vortex active after the MAX", pb.memory[TICKS] > 0,
          f"ticks={pb.memory[TICKS]}")
    # Swim away onto the far body. Keep HP/i-frames honest so a
    # contact thump cannot be mistaken for a vortex hit.
    put16(pb, PLAYER + 9, 16)
    put16(pb, PLAYER + 11, 16)
    pb.memory[HP] = pb.memory[PLAYER + 1]
    pb.memory[IFRAMES] = 60
    near_frame = far_frame = None
    near_hp, far_hp = near_hp0, far_hp0
    for frame in range(220):
        pb.tick()
        n = pb.memory[near + 14]
        f = pb.memory[far + 14]
        if near_frame is None and n < near_hp:
            near_frame = frame
        if far_frame is None and f < far_hp:
            far_frame = frame
        near_hp, far_hp = n, f
        if near_frame is not None and far_frame is not None:
            break
        if not pb.memory[TICKS] and frame > 10:
            break
    check("anchor: body at the cast point is still hit after Picsean leaves",
          near_frame is not None,
          f"near_frame={near_frame} far_frame={far_frame}")
    check("anchor: body under Picsean's new tile is not hit first",
          far_frame is not None and near_frame < far_frame,
          f"near={near_frame} far={far_frame}")



def try_fire_max(pb, ticks=8):
    """Press A without requiring the MAX to spend Will."""
    pb.button_press("right")
    pb.button_press("a")
    for _ in range(ticks):
        pb.tick()
    pb.button_release("a")
    pb.button_release("right")


def recharge_cooldown(pb):
    """After Tide Vortex the next MAX is locked for 360 frames.

    Spec: docs/superpowers/specs/2026-11-17-picsean-vortex-cooldown.md
    Will still banks on the ordinary first-pip clock (180 frames at
    SPD 4). A press during the remaining lock is a normal BubbleBolt
    and does not spend the banked pip. At 360 frames the MAX recasts.
    """
    arm(pb)
    pb.memory[PLAYER + 7] = 4
    pb.memory[PLAYER + 44] = 7
    pb.memory[addr("_will_charge_fraction")] = 0
    fire_max(pb)
    check("vortex spent every banked pip",
          pb.memory[PLAYER + LEVEL_OFFSET] == 0
          and pb.memory[PLAYER + WILL_OFFSET] == 0)
    # Let the first vortex finish, then the ordinary 3s pip bank.
    for _ in range(180):
        pb.memory[IFRAMES] = 60
        pb.tick()
    check("ordinary first pip still banks at 180 frames (3.00s)",
          pb.memory[PLAYER + LEVEL_OFFSET] >= 1,
          f"level={pb.memory[PLAYER + LEVEL_OFFSET]} "
          f"charge={pb.memory[PLAYER + WILL_OFFSET]}")
    try_fire_max(pb, ticks=8)
    check("old 3s recast is locked; the banked pip is kept",
          pb.memory[PLAYER + LEVEL_OFFSET] >= 1
          and pb.memory[TICKS] == 0,
          f"level={pb.memory[PLAYER + LEVEL_OFFSET]} ticks={pb.memory[TICKS]}")
    # 180 + 8 try-fire ticks; 360 - 188 = 172 more, plus slack.
    for _ in range(172):
        pb.memory[IFRAMES] = 60
        pb.tick()
    fire_max(pb)
    check("vortex recasts at 360 frames (6.00s)",
          pb.memory[TICKS] > 0 and pb.memory[PLAYER + LEVEL_OFFSET] == 0,
          f"ticks={pb.memory[TICKS]} level={pb.memory[PLAYER + LEVEL_OFFSET]}")


def crowded_updates(cast):
    """Logic updates over 96 frames in a 14-body room (fresh boot each run).

    Bodies are STOP-frozen with HP refilled every frame so the load is the
    same with and without the vortex. This room already has only a few
    scanlines of slack when idle, so it is a worst case, not typical play.
    """
    pb = boot(3)
    try:
        arm(pb)
        if not cast:
            pb.memory[PLAYER + WILL_OFFSET] = 0
            pb.memory[PLAYER + LEVEL_OFFSET] = 0
        slots = [make_crawler(pb, 8 + i, 16 + (i % 7) * 20,
                              20 if i < 7 else 100)
                 for i in range(14)]
        pb.memory[COUNT] = 14

        def refresh():
            for i, e in enumerate(slots):
                pb.memory[e] = 2
                pb.memory[e + 1] |= 0x07
                pb.memory[e + 14] = 200
                pb.memory[STATUS_KIND + 8 + i] = QSTATUS_STOP
                pb.memory[STATUS_TICKS + 8 + i] = 250

        refresh()
        if cast:
            fire_max(pb)
        else:
            pb.tick(2)
        previous, updates = pb.memory[CLOCK], 0
        for _ in range(96):
            refresh()
            pb.tick()
            current = pb.memory[CLOCK]
            updates += (current - previous) & 255
            previous = current
        return updates
    finally:
        pb.stop(save=False)


def gif(pb, path):
    from PIL import Image
    pb.tick(60)
    put16(pb, PLAYER + 9, 72)
    put16(pb, PLAYER + 11, 60)
    pb.memory[LCK] = 0
    for i, (x, y) in enumerate(((24, 24), (120, 24), (24, 100), (120, 100),
                                (40, 64), (110, 64), (76, 20), (76, 104),
                                (10, 60), (144, 60))):
        e = make_crawler(pb, 10 + i, x, y, hp=10, stop=False)
        if i & 1:                     # hornets between the crawlers
            pb.memory[e + 12] = 21
            pb.memory[e + 13] = 5
            pb.memory[e + 17] = 2
        else:
            pb.memory[e + 13] = 3
    for k, (x, y) in enumerate(((40, 30), (120, 44), (50, 110), (130, 110))):
        make_shot(pb, 24 + k, x, y)
    pb.memory[COUNT] = 10
    pb.tick(34)                       # let the room stream the enemy art
    pb.memory[PLAYER + WILL_OFFSET] = 90
    pb.memory[PLAYER + LEVEL_OFFSET] = 1
    frames = [pb.screen.image.copy().convert("RGB")]
    pb.button_press("right")
    pb.button_press("a")
    for i in range(130):
        pb.tick()
        if i == 6:
            pb.button_release("a")
            pb.button_release("right")
        if i == 18:
            # Swim toward the upper-left so the GIF shows the eye
            # staying at the cast tile.
            pb.button_press("left")
            pb.button_press("up")
        if i == 70:
            pb.button_release("left")
            pb.button_release("up")
        frames.append(pb.screen.image.copy().convert("RGB"))
    frames = [f.resize((320, 288), Image.NEAREST) for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=17, loop=0)
    print(f"  gif {path} ({len(frames)} frames)")


def main():
    pb = boot(3)
    try:
        contract(pb)
        anchored(pb)
        recharge_cooldown(pb)
    finally:
        pb.stop(save=False)
    idle = crowded_updates(cast=False)
    vortex = crowded_updates(cast=True)
    print(f"  crowded 14-body room: idle={idle} vortex={vortex} "
          "logic updates / 96 frames")
    # The old Moon Tide scored 65 here; zero cost is not reachable in a
    # room with ~4 lines of idle slack.
    check("crowded room: at least the old Moon Tide's rate",
          vortex >= 70 and vortex * 100 >= idle * 75,
          f"idle={idle} vortex={vortex}")
    out = os.environ.get("QUINTRA_VORTEX_GIF")
    if out:
        pb = boot(3)
        try:
            gif(pb, out)
        finally:
            pb.stop(save=False)
    print("[picsean-tide-vortex] PASS spiral front sweeps the room; shots "
          "washed out; heavy damage capped; crowded rate beats Moon Tide")


if __name__ == "__main__":
    main()
