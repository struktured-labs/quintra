#!/usr/bin/env python3
"""ROM regression: final boss art and behavior differ from the first boss."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_direction, dungeon_size,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20
SPR_BOSS_BIG = 40


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(
    addr,
    ("_run_state", "_player", "_entities", "_room_tilemap",
     "_procgen_current_room_is_large", "_room_world_width",
     "_room_world_height", "_room_camera_x", "_room_camera_y"),
)
ENEMY_STATUS = addr("_enemy_status_kind")


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def enter_boss(stage, keep_open=False):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    target = STAGE_BOSS_ROOM[stage]
    pb.memory[RS + 1] = target - 1
    pb.memory[RS + 11] = stage
    pb.memory[RS + 6] = 0xFF
    # Boss identity begins at an authored compact sanctuary threshold after
    # rewriting only the logical counter. Normalize the real wide foyer state
    # before taking that synthetic predecessor edge.
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    # The sanctuary before each boss correctly requires that stage's Rift
    # Sigil. This identity harness is sampling an already-qualified stage,
    # so grant that objective instead of mistaking its progression gate for
    # a failed room transition.
    put16(pb, RS + 23, 1 << stage)
    pb.memory[RS + 27] = (1 << 0) | (1 << 3) | (1 << 6) | (1 << 7)
    pb.memory[RS + 28] |= (1 << 2) | (1 << 7)
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    source_local = target - 1 - STAGE_START[stage]
    target_local = target - STAGE_START[stage]
    direction = dungeon_direction(source_local, target_local)
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * ROOM_W + tx] = 3
    x, y = {
        0: (72, 0), 1: (144, 60),
        2: (72, 120), 3: (0, 60),
    }[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(50):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"could not enter boss stage {stage}"
    # room_counter advances at transition start; allow the banked generator
    # and fade-in to finish before inspecting entities and loaded OBJ tiles.
    for _ in range(60):
        pb.tick()

    boss = None
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2 and pb.memory[ep + 17] == 1:
            boss = ep
            break
    active = [
        (pb.memory[EN + i * 28], pb.memory[EN + i * 28 + 1],
         pb.memory[EN + i * 28 + 17], pb.memory[EN + i * 28 + 19])
        for i in range(32) if pb.memory[EN + i * 28 + 1] & 1
    ]
    assert boss is not None, f"stage {stage} did not spawn its large boss: {active}"
    assert pb.memory[boss + 12] == SPR_BOSS_BIG, "large boss tile slot drifted"
    assert pb.memory[boss + 20] & 1, "boss giant flag missing"
    assert pb.memory[boss + 19] == stage, "boss attack variant does not match stage"

    # CPU-visible VRAM reads are blocked during active LCD transfer. This
    # disposable test instance can disable the LCD after taking its screenshot
    # and then inspect the loaded OBJ bytes directly.
    shot = ROOT / "tmp" / f"boss-stage-{stage}.png"
    shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(shot)
    pb.memory[0xFF40] = pb.memory[0xFF40] & 0x7F
    pb.memory[0xFF4F] = 0  # OBJ tile bytes live in VRAM bank 0
    art = bytes(pb.memory[0x8000 + SPR_BOSS_BIG * 16:
                          0x8000 + (SPR_BOSS_BIG + 16) * 16])
    if keep_open:
        # Restore LCD before handing the live encounter to the phase test.
        pb.memory[0xFF40] = pb.memory[0xFF40] | 0x80
        return pb, boss
    pb.stop(save=False)
    return art


def main():
    art = [enter_boss(stage) for stage in range(9)]
    assert len(set(art)) == 9, "not all nine stage bosses load distinct VRAM art"
    colossus, void_lord = art[0], art[8]
    assert colossus != void_lord, (
        f"Void Lord VRAM art equals first Colossus "
        f"(nonzero={sum(b != 0 for b in colossus)}, first={colossus[:8].hex()})"
    )
    differing = sum(a != b for a, b in zip(colossus, void_lord))
    assert differing >= 8, f"Void Lord crown is not visually substantial ({differing} bytes)"
    pb, void_lord = enter_boss(8, keep_open=True)
    # The final encounter remains armored and substantially longer than a
    # normal boss, but its 220-HP cap avoids a deterministic late-collapse loss
    # after the full World Collapse positioning test.
    assert pb.memory[void_lord + 14] == 220, (
        f"Void Lord HP balance cap drifted: {pb.memory[void_lord + 14]}")
    pb.stop(save=False)
    pb, temple = enter_boss(6, keep_open=True)
    assert pb.memory[temple + 14] == 230, (
        f"Golden Temple HP balance cap drifted: {pb.memory[temple + 14]}")
    pb.stop(save=False)
    pb, hydra = enter_boss(7, keep_open=True)
    # Bloodmoon's Hydra is the high-damage, sustained-weave endurance boss.
    # Its finite 150-HP window is still deliberately lower than the static
    # late-game caps because its streams remain live for the entire fight,
    # while keeping the strongest base kit above an eight-second ideal floor.
    assert pb.memory[hydra + 14] == 150, (
        f"Bloodmoon Hydra endurance window drifted: {pb.memory[hydra + 14]}")
    pb.stop(save=False)
    pb, boss = enter_boss(0, keep_open=True)
    assert pb.memory[boss + 14] == 220, (
        f"starter Colossus pacing drifted: {pb.memory[boss + 14]}")
    assert pb.memory[boss + 25] == 0xFF, "early Colossus contact body drifted"
    max_hp = pb.memory[boss + 23]  # ai_data[6], captured by boss_tick
    assert max_hp > 1, "boss never captured its starting HP for enrage"
    hostile_count = lambda: sum(
        pb.memory[EN + i * 28] == 1
        and pb.memory[EN + i * 28 + 1] & 1
        and not (pb.memory[EN + i * 28 + 1] & 0x10)
        for i in range(32)
    )
    # This test enters an already-live Colossus, so its opening 8-ring may
    # still occupy the shared entity table. Clear those disposable shots
    # before forcing the authored half-health Prism Lance.
    for i in range(32):
        ep = EN + i * 28
        if (pb.memory[ep] == 1 and pb.memory[ep + 1] & 1
                and not (pb.memory[ep + 1] & 0x10)):
            pb.memory[ep] = pb.memory[ep + 1] = 0
    # This is an identity contract for the authored Prism geometry, not a Mute
    # contract. Class-select input can deterministically tag the live boss with
    # a condition before this synthetic health rewrite, so normalize it here;
    # status behavior has its own direct ROM suite.
    pb.memory[ENEMY_STATUS + (boss - EN) // 28] = 0
    # Exercise the phase break in the new eastern chamber, where the warning
    # must remain a real world-space projectile pattern rather than depending
    # on the compact projection's decorative tile footprint.
    put16(pb, boss + 3, 160)
    put16(pb, boss + 7, 64)
    pb.memory[boss + 14] = max_hp // 2
    saw_warning = False
    prism_shots = 0
    # The signature announces its captured lane for 48 gameplay beats before
    # firing. Keep the observer invulnerable and wait for that complete event.
    for _ in range(160):
        pb.memory[PL + 15] = 255
        pb.memory[ENEMY_STATUS + (boss - EN) // 28] = 0
        pb.tick()
        if pb.memory[boss + 20] & 0x40:
            saw_warning = True
        if (saw_warning and not (pb.memory[boss + 20] & 0x40)
                and pb.memory[boss + 18] >= 30
                and hostile_count() >= 3):
            prism_shots = hostile_count()
            break
    assert saw_warning, "boss did not telegraph its half-health signature"
    assert pb.memory[boss + 20] & 0x80, "boss signature did not latch as spent"
    assert pb.memory[boss + 18] >= 30, "signature lost its readable recovery beat"
    assert prism_shots == 3, (
        f"Crystal Colossus did not emit its three-wide Prism Lance: {prism_shots}")
    pb.stop(save=False)
    pb, serpent = enter_boss(1, keep_open=True)
    assert pb.memory[serpent + 14] == 240, (
        f"Verdant Serpent HP pacing drifted: {pb.memory[serpent + 14]}")
    assert pb.memory[serpent + 25] == 0xDD, (
        "Verdant's mobile Serpent did not receive its fair contact body")
    pb.stop(save=False)
    pb, cinder = enter_boss(2, keep_open=True)
    # Ember is now two fights in one: five 24-HP Kilnback bands followed by a
    # 120-HP Cinder Rex, with damage restricted to visible vent windows.
    assert pb.memory[cinder + 14] == 240, (
        f"Kilnback/Cinder Rex pacing cap drifted: {pb.memory[cinder + 14]}")
    pb.stop(save=False)
    pb, frost = enter_boss(3, keep_open=True)
    assert pb.memory[frost + 14] == 150, (
        f"Frost Vault HP balance cap drifted: {pb.memory[frost + 14]}")
    assert pb.memory[frost + 25] == 0xDD, (
        "Frost Vault giant did not receive its tighter late-run contact body")
    pb.stop(save=False)
    print(f"[boss-id] PASS 9/9 distinct runtime silhouettes; "
          f"Colossus vs crowned Void Lord differs {differing}/256 bytes; "
          f"variants 0..8; charged Prism Lance adds {prism_shots} shots")


if __name__ == "__main__":
    main()
