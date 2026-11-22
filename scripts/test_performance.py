#!/usr/bin/env python3
"""ROM regression: CGB double-speed keeps a dense room near video rate."""
import re
import os
import json
import hashlib
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


FC, EN, TM, WW, WH, CX, CY, EC, PL = map(addr, (
    "_loop_frame_counter", "_entities", "_room_tilemap",
    "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y",
    "_entity_enemy_count", "_player",
))


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (i * 8)) & 0xFF


def loop_frames(pb):
    return pb.memory[FC] | (pb.memory[FC + 1] << 8)


SCREEN = addr("_loop_current_screen")


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def reach_title(pb):
    """Power-on can land in the intro for well over 240 frames."""
    for _ in range(600):
        if pb.memory[SCREEN] == 1:
            return
        pb.tick()
    if pb.memory[SCREEN] != 1:
        press(pb, "start")
        for _ in range(180):
            if pb.memory[SCREEN] == 1:
                return
            pb.tick()


def wait_room(pb, limit=400):
    skipped = False
    for i in range(limit):
        if pb.memory[SCREEN] == 5:
            return
        if pb.memory[SCREEN] == 6 and not skipped and i >= 8:
            press(pb, "start")
            skipped = True
            continue
        pb.tick()


def boot_room():
    from quintra_vignettes import mute_after_class_select
    pb = PyBoy(str(ROM), window="null", cgb=True)
    reach_title(pb)
    pb.tick(30)
    press(pb, "start")
    for _ in range(200):
        if pb.memory[SCREEN] == 2:
            break
        pb.tick()
    pb.tick(30)
    press(pb, "a")  # Wolfkin, first class
    mute_after_class_select(pb, ROM, settle=8)
    wait_room(pb)
    for btn in ("a", "b", "start", "select", "right", "left", "up", "down"):
        pb.button_release(btn)
    pb.tick(90)
    assert pb.memory[0xFF4D] & 0x80, "cartridge never entered CGB double-speed mode"
    pb.memory[PL + 1] = pb.memory[PL + 2] = 240
    return pb


def make_fixed_crawlers(pb):
    """Seed-stable 16-crawler roster.

    The opening pack is rng_seed(loop_frame_counter) at run_init, and the
    historical converter only retargets species on whatever foyer rolled.
    That layout (on-camera count, Blue Crawler pattern identities 1/2/3,
    leftover shots) can swing the 167 floor by several loop frames: the
    same converter scored 168 on one Aftershock boot and 162 on another,
    while max-Will landed 163 with hooks reverted. Plant a fixed layout
    instead of converting the roll. Do not lower the 167 floor.

    3 on-camera / 13 off-camera in a 248x248 room, leftover shots cleared,
    walking clocks staggered. On-camera bodies are two type-1 darts and
    one type-3 viral pulse with clocks that fire once in the 180-tick
    window — an authentic mid-pack load, not three stacked type-2 volleys
    and not an empty 180/180 dart-only room. Off-camera bodies sit far
    enough (x>=216 or y>=200 at camera 0,0; west/north of a shifted
    camera) that 0.25 px/frame wander cannot enter the padded 175x151
    view in 180 ticks. ai_data[0] stays 0 (ENEMY_BLUE_CRAWLER).
    """
    for i in range(32):
        ep = EN + i * 28
        for b in range(28):
            pb.memory[ep + b] = 0

    cx = pb.memory[CX]
    cy = pb.memory[CY]
    # Camera-relative so a west/north foyer entry still keeps 3 in view.
    on_cam = (
        (cx + 40, cy + 40, 1, 80),
        (cx + 100, cy + 48, 1, 50),
        (cx + 56, cy + 96, 3, 80),
    )
    off_cam = []
    if cx + 175 < 248:
        xs = (cx + 216, cx + 228)
        for i, y in enumerate((32, 48, 64, 80, 96, 112, 128)):
            off_cam.append((xs[i % 2], y if cy + y < 248 else 240))
    else:
        for i, y in enumerate((32, 48, 64, 80, 96, 112, 128)):
            off_cam.append((16 if i % 2 == 0 else 28, y))
    for pos in ((32, 200), (64, 216), (96, 200), (128, 216), (216, 216),
                (200, 200), (184, 216)):
        if len(off_cam) >= 13:
            break
        if pos not in off_cam:
            off_cam.append(pos)
    off_cam = off_cam[:13]

    spots = [(x, y, ident, clock, 1) for (x, y, ident, clock) in on_cam]
    spots += [(x, y, 1, 1, 0) for (x, y) in off_cam]
    pb.memory[EC] = len(spots)
    for i, (x, y, ident, clock, on_screen) in enumerate(spots):
        ep = EN + i * 28
        pb.memory[ep] = 2  # ENT_ENEMY
        pb.memory[ep + 1] = 0x07 if on_screen else 0x03
        put32(pb, ep + 2, x << 8)
        put32(pb, ep + 6, y << 8)
        pb.memory[ep + 10] = pb.memory[ep + 11] = 0
        pb.memory[ep + 12] = 20  # sprite_tile
        pb.memory[ep + 13] = 3   # palette
        pb.memory[ep + 14] = 8   # hp
        pb.memory[ep + 15] = 0   # walker state
        # Stagger walker state_timer so retargets are not lockstep.
        # Must not write ai_data[0] (ep+17): that is the content id.
        pb.memory[ep + 16] = (i * 3 + 5) & 0x1F or 1
        pb.memory[ep + 17] = 0  # ENEMY_BLUE_CRAWLER
        for offset in range(18, 25):
            pb.memory[ep + offset] = 0
        # ai_data[3]/[4] are the crawler pattern clock and identity.
        # Identity 1 = dart, 3 = viral pulse (8 radial shots).
        pb.memory[ep + 20] = clock
        pb.memory[ep + 21] = ident
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1


def main():
    pb = boot_room()
    # Opening packs need a beat after foyer entry before the mixed-AI
    # cost settles; measuring immediately can miss the 18-body floor by 1.
    pb.tick(60)

    before = loop_frames(pb)
    pb.tick(180)
    generated = (loop_frames(pb) - before) & 0xFFFF
    population = []
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2 and pb.memory[ep + 1] & 1:
            population.append({
                "slot": i,
                "awake": bool(pb.memory[ep + 1] & 4),
                "x": pb.memory[ep + 3],
                "y": pb.memory[ep + 7],
            })
    awake = sum(enemy["awake"] for enemy in population)
    assert 14 <= len(population) <= 18, (
        f"opening district population drifted: {len(population)}")
    assert 1 <= awake < len(population), (
        f"camera-sector sleeping drifted: awake={awake}/{len(population)}")
    # Asset uploads affect DIV before the run seed is mixed, so an authored
    # atlas can legitimately move this probe between 14- and 18-body rolls.
    # Preserve the 55 Hz floor at fourteen bodies and budget three loop turns
    # per additional actor instead of pretending those rooms cost the same.
    generated_floor = 165 - max(0, len(population) - 14) * 3
    assert generated >= generated_floor, (
        f"generated mixed-AI room missed 55 Hz: {generated}/180 loop frames"
    )

    # The shipped v0.20.5 clean-room baseline was 171/180 (57 Hz) for sixteen
    # enemies. A discovered Road Echo can become a seventeenth 16x16 OAM actor;
    # the generated-room floor above retains that budget while an undiscovered
    # opening no longer receives the follower for free. The projectile-only
    # saturation fence below remains independent of either state.
    # Fill 12/32 entity slots with long-lived projectiles over known floor.
    # This exercises banked updates, collision scans, animation, and OAM writes
    # without using host wall-clock speed or depending on one procgen seed.
    for y in range(3, 14):
        for x in range(3, 17):
            pb.memory[TM + y * ROOM_W + x] = 1
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[EC] = 0
    for i in range(12):
        ep = EN + i * 28
        x = 32 + (i % 7) * 16
        y = 24 + (i // 7) * 24
        pb.memory[ep] = 1          # ENT_PROJECTILE
        pb.memory[ep + 1] = 0x03  # active/alive hostile bullet-hell load
        put32(pb, ep + 2, x << 8)
        put32(pb, ep + 6, y << 8)
        pb.memory[ep + 10] = pb.memory[ep + 11] = 0
        pb.memory[ep + 12] = 28
        pb.memory[ep + 13] = 2
        pb.memory[ep + 14] = 1
        pb.memory[ep + 16] = 255
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1

    before = loop_frames(pb)
    pb.tick(180)
    loops = (loop_frames(pb) - before) & 0xFFFF
    active = sum(pb.memory[EN + i * 28 + 1] & 1 for i in range(32))
    pb.stop(save=False)

    # Asset loading legitimately advances DIV before run seeding, so a new
    # sprite atlas can change the opening species without changing game code.
    # Use a fresh boot and plant a seed-stable crawler roster before
    # enforcing the historical apples-to-apples 57 Hz fence.
    fixed_pb = boot_room()
    make_fixed_crawlers(fixed_pb)
    before = loop_frames(fixed_pb)
    fixed_pb.tick(180)
    ordinary = (loop_frames(fixed_pb) - before) & 0xFFFF
    sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=ROOT/'builds'/f'room-performance-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    fixed_pb.screen.image.save(str(out/'fixed-roster.png'))
    fixed_pb.stop(save=False)

    (out/'capture.json').write_text(json.dumps(dict(
        rom_sha256=sha, script_sha256=script_sha,
        fixture='Fresh boot; generated district, stationary shot saturation, planted 16-crawler roster (2 darts + 1 viral pulse on-camera). Native 180-LCD-frame windows; no stalls removed.',
        generated=generated, generated_floor=generated_floor,
        fixed_roster=ordinary, fixed_floor=167, dense=loops, dense_floor=135,
        population=population, active_projectiles=active,
        passed=ordinary>=167 and active>=10 and loops>=135),indent=2))
    print(f'[performance] measured generated={generated}, fixed={ordinary}, dense={loops} /180',flush=True)

    assert ordinary >= 167, (
        f"fixed-roster room missed video rate: {ordinary}/180 loop frames"
    )
    assert active >= 10, f"stress load evaporated before measurement ({active}/12)"
    # Twelve simultaneous hostile shots produce the v0.20.5 saturated
    # baseline of 135/180 (45 Hz). This is a regression fence, not a claim
    # that the existing engine has already reached the future 80% target.
    assert loops >= 135, (
        f"dense room fell below release baseline: {loops}/180 loop frames"
    )
    print(f"[performance] PASS double-speed generated={generated}/180, "
          f"fixed-roster={ordinary}/180, "
          f"dense={loops}/180, population={len(population)}, "
          f"awake={awake}, active_projectiles={active}/12")


if __name__ == "__main__":
    main()
