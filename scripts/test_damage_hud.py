#!/usr/bin/env python3
"""ROM contract: damage redraws hearts and preserves readable hit recovery."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, RS, TM, SCREEN = map(addr, (
    "_player", "_entities", "_run_state", "_room_tilemap", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[EN + i] = 0


def assert_spike_stumble(pb):
    """A safe adjacent tile must break a spike contact without a second hit."""
    clear_entities(pb)
    pb.memory[RS + 17] = 0
    # Player feet center is x+8,y+12. Build a tiny guaranteed-safe cross
    # around tile (10,8), with the center as the only spike.
    for ty in range(6, 11):
        for tx in range(8, 13):
            pb.memory[TM + ty * 20 + tx] = 1  # BGT_FLOOR
    pb.memory[TM + 8 * 20 + 10] = 31          # BGT_SPIKES
    pb.memory[PL + 9] = 72
    pb.memory[PL + 10] = 0
    pb.memory[PL + 11] = 52
    pb.memory[PL + 12] = 0
    pb.memory[PL + 2] = 2
    pb.memory[PL + 15] = 0
    pb.memory[PL + 20] = 0
    for _ in range(12):
        pb.tick()
        if pb.memory[PL + 2] == 1:
            break
    assert pb.memory[PL + 2] == 1, "spike fixture did not deal its one hit"
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    center_tile = pb.memory[TM + ((py + 12) // 8) * 20 + ((px + 8) // 8)]
    assert center_tile != 31 and (px, py) != (72, 52), (
        f"spike recovery left hero on hazard at {px},{py}, tile={center_tile}")


def take_hostile_hit(pb, world_mode=0, boss_body=False, void_lord_body=False):
    """Inject one real overlapping hostile and return the resulting iframe count."""
    clear_entities(pb)
    pb.memory[RS + 17] = world_mode
    pb.memory[PL + 2] = 8
    pb.memory[PL + 15] = 0
    pb.memory[PL + 20] = 0
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    hostile = EN
    if boss_body or void_lord_body:
        pb.memory[hostile] = 2           # ENT_ENEMY
        pb.memory[hostile + 1] = 3       # active + alive
        pb.memory[hostile + 14] = 10
        pb.memory[hostile + 25] = 0xEE   # 16x16/32x32-style collision body
        pb.memory[hostile + 17] = 1      # ENEMY_STONE_SENTINEL
        pb.memory[hostile + 19] = 8 if void_lord_body else 0
        pb.memory[hostile + 20] = 1      # giant boss flag
        pb.memory[hostile + 26] = 2
    else:
        pb.memory[hostile] = 1           # ENT_PROJECTILE
        pb.memory[hostile + 1] = 3       # active hostile projectile
        pb.memory[hostile + 14] = 1
        pb.memory[hostile + 16] = 20
        pb.memory[hostile + 25] = 0x77
        pb.memory[hostile + 26] = 1
    # A projectile's tiny 5x5 footprint needs its origin at the hero's
    # center; the giant body instead begins at the hero origin so the real
    # 6x6 center hurtbox is strictly inside its 14x14 collision box.
    put_fix8(pb, hostile + 2, px if (boss_body or void_lord_body) else px + 5)
    put_fix8(pb, hostile + 6, py if (boss_body or void_lord_body) else py + 9)
    for _ in range(60):
        pb.tick()
        if pb.memory[PL + 2] == 7:
            return pb.memory[PL + 15]
    raise AssertionError(
        "injected hostile did not damage player: "
        f"hp={pb.memory[PL + 2]} iframes={pb.memory[PL + 15]} shield={pb.memory[PL + 20]} "
        f"enemy={pb.memory[hostile]}/{pb.memory[hostile + 1]} "
        f"id={pb.memory[hostile + 17]} variant={pb.memory[hostile + 19]}/"
        f"{pb.memory[hostile + 20]} pos="
        f"{pb.memory[hostile + 3]},{pb.memory[hostile + 7]} player="
        f"{pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)},"
        f"{pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)}"
    )


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5
    assert (pb.memory[PL], pb.memory[PL + 1], pb.memory[PL + 2]) == (0, 12, 12), (
        "Wolfkin no longer starts with the promised six-heart reserve: "
        f"class={pb.memory[PL]} hp_max={pb.memory[PL + 1]} hp={pb.memory[PL + 2]}"
    )

    # Force a known four-heart state and let the public HUD redraw path settle.
    pb.memory[PL + 1] = 8
    pb.memory[PL + 2] = 8
    pb.memory[PL + 6] = 0
    pb.memory[PL + 15] = 0
    clear_entities(pb)
    for _ in range(2):
        pb.tick()
    pb.memory[0xFF4F] = 0
    before = bytes(pb.memory[0x9C00:0x9C08])

    iframes = take_hostile_hit(pb)
    assert pb.memory[PL + 2] == 7, (
        f"hostile projectile did not damage player: hp={pb.memory[PL + 2]} "
        f"iframes={iframes}"
    )
    assert iframes == 30, f"ordinary dungeon hit grace drifted: {iframes}"
    pb.memory[0xFF4F] = 0
    after = bytes(pb.memory[0x9C00:0x9C08])
    assert before != after, f"heart row stayed stale after damage: {before.hex()}"
    assert after[3] in (5, 6) and after[:3] == bytes([4, 4, 4]), \
        f"damage did not visibly reduce the fourth heart: {after.hex()}"

    # Riftwild is a non-mandatory traversal graph: recovery is deliberately
    # long enough to leave a body-pin before the next contact check.
    assert take_hostile_hit(pb, world_mode=1) == 60, \
        "Riftwild contact recovery is no longer the promised 60 frames"
    # A giant body is still dangerous, but its projectile pattern is the main
    # test. A 45-frame grace prevents unreadable re-contact without weakening
    # normal enemies or projectiles.
    assert take_hostile_hit(pb, boss_body=True) == 45, \
        "ordinary giant body-contact recovery is no longer 45 frames"
    assert take_hostile_hit(pb, void_lord_body=True) == 45, \
        "Void Lord body-contact recovery is no longer the promised 45 frames"
    assert_spike_stumble(pb)
    pb.stop(save=False)
    print("[damage-hud] OK: Wolfkin six-heart start, heart redraw, "
          "30/60/45-frame recovery, safe spike stumble")


if __name__ == "__main__":
    main()
