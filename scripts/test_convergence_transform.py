#!/usr/bin/env python3
"""Live-ROM contract: a full-MP A+B chord visibly ascends every champion."""

import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SPR_CLASS_BASE = 0
SPR_CLASS_STRIDE = 4
SPR_CLASS_ASCENDED_BASE = 102


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER, ENTITIES, TRANSFORM = map(
    addr, ("_player", "_entities", "_room_transform_ticks")
)


def boot(class_moves):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    for _ in range(class_moves):
        pb.button("down")
        pb.tick(8)
    pb.button("a")
    pb.tick(140)
    # Make the test about the player-visible chord, not a generated room's
    # incidental contact damage or projectiles.
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0
    return pb


def oam_tiles(pb):
    return [pb.memory[0xFE00 + sprite * 4 + 2] for sprite in range(4)]


def wait_for_visible_ascended_pose(pb, expected):
    # Convergence grants a short invulnerability window.  During its blink
    # frames the metasprite is intentionally parked, so sample a visible
    # frame rather than confusing that safety cue with a missing transform.
    for _ in range(16):
        pb.tick()
        if oam_tiles(pb) == expected:
            return
    raise AssertionError(
        f"ascended OAM never appeared: got={oam_tiles(pb)} expected={expected}"
    )


def assert_class(class_id, name, check_expiry=False):
    pb = boot(class_id)
    assert pb.memory[PLAYER] == class_id, f"did not enter as {name}"
    pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]  # fill MP through live input
    pb.memory[PLAYER + 19] = 0                      # A+B cooldown is ready

    # Both presses must arrive before one emulated frame: the cartridge uses
    # an actual simultaneous edge, rather than treating a sequential combo as
    # a transformation.
    pb.button_press("a")
    pb.button_press("b")
    pb.tick()
    pb.button_release("a")
    pb.button_release("b")

    # PyBoy submits button transitions to its emulated hardware queue.  The
    # cartridge polls them a couple of frames later, so wait for that genuine
    # poll instead of assuming the host tick that queued the chord is it.
    for _ in range(8):
        if pb.memory[TRANSFORM] > 0:
            break
        pb.tick()
    assert pb.memory[TRANSFORM] > 0, f"{name} A+B chord did not start Convergence"
    assert pb.memory[PLAYER + 4] == 0, f"{name} Convergence did not consume full MP"
    expected = [SPR_CLASS_ASCENDED_BASE + class_id * SPR_CLASS_STRIDE + part
                for part in range(4)]
    wait_for_visible_ascended_pose(pb, expected)

    if check_expiry:
        # 135 steps at eight room frames is 18 seconds.  Cross that interval
        # and prove the player returns to the normal, non-ascended metasprite.
        pb.tick(1120)
        assert pb.memory[TRANSFORM] == 0, "Convergence visual state exceeded 18 seconds"
        normal = [SPR_CLASS_BASE + part for part in range(4)]
        for _ in range(16):
            pb.tick()
            if oam_tiles(pb) == normal:
                break
        else:
            raise AssertionError(
                f"Convergence expiry left Wolfkin ascended: got={oam_tiles(pb)}"
            )
    pb.stop(save=False)


def main():
    names = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")
    for class_id, name in enumerate(names):
        assert_class(class_id, name, check_expiry=(class_id == 0))
    print("[convergence-transform] PASS five ascended metasprites; 18s expiry restores base pose")


if __name__ == "__main__":
    main()
