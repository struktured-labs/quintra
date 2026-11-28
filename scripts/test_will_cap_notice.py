#!/usr/bin/env python3
"""Raising the Will cap is announced, and the HUD digit starts at 0 (#208).

The HUD digit is the number of Will tiers stored: 0 at the start of a run,
with room to hold one. The Titan Glove, Tide Raft and Rift Hook each let
the hero hold one more. That used to happen silently; the window now says
WILL+1. The Rift Glass does not raise the cap and says nothing.

The manual must describe the same thing: it used to say "You begin at
tier 1" beside a digit that reads 0.
"""
from pathlib import Path

from test_heart_hud import notice, spawn_heart
from test_will_max import LEVEL_OFFSET, PLAYER, addr, boot, clear_arena

ROOT = Path(__file__).resolve().parent.parent
PICKUP_WAYGEAR = 22
WAYGEAR_OWNED = 44
WILL_UP = (80, 77, 81, 81, 95, 10)        # W I L L + 1
WIN = 0x9C00
SCREEN = addr("_loop_current_screen")
SCREEN_ROOM = 5
HUD_DIGIT_0 = 9
GEAR = ("Titan Glove", "Tide Raft", "Rift Hook", "Rift Glass")


def cap(pb):
    owned = pb.memory[PLAYER + WAYGEAR_OWNED]
    return 1 + (owned & 1) + ((owned >> 1) & 1) + ((owned >> 2) & 1)


def grant(pb, gear):
    ep = spawn_heart(pb)                  # a pickup under the hero's feet
    pb.memory[ep + 17] = PICKUP_WAYGEAR
    pb.memory[ep + 18] = gear
    seen = False
    for frame in range(600):
        pb.memory[PLAYER + 15] = 200
        pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]
        # The claim ceremony and its dialog want A; tap it throughout.
        if frame % 20 == 10:
            pb.button("a")
        pb.tick()
        if notice(pb) == WILL_UP:
            seen = True
            break
    assert pb.memory[PLAYER + WAYGEAR_OWNED] & (1 << gear), (
        f"{GEAR[gear]} was not granted")
    return seen


def settle(pb):
    """Finish the claim ceremony and its dialog; let the notice lane clear."""
    for frame in range(480):
        pb.memory[PLAYER + 15] = 200
        if frame % 20 == 10:
            pb.button("a")
        pb.tick()
    assert pb.memory[SCREEN] == SCREEN_ROOM, (
        f"stuck on screen {pb.memory[SCREEN]} after a Waygear claim")


def main():
    manual = (ROOT / "docs/manual/content/the-hud.md").read_text()
    assert "You begin at tier 1" not in manual, (
        "the manual still says the Will digit begins at tier 1")
    assert "the digit reads 0" in manual and "WILL+1" in manual

    pb = boot(0)
    clear_arena(pb)
    for _ in range(120):
        pb.memory[PLAYER + 15] = 200
        pb.tick()
    assert pb.memory[PLAYER + LEVEL_OFFSET] == 0 and cap(pb) == 1
    assert pb.memory[0, WIN + 12] == HUD_DIGIT_0, (
        f"the Will digit does not start at 0: tile {pb.memory[0, WIN + 12]}")

    for gear in (0, 1, 2):
        before = cap(pb)
        assert grant(pb, gear), (
            f"{GEAR[gear]} raised the Will cap without saying WILL+1")
        assert cap(pb) == before + 1
        settle(pb)
    before = cap(pb)
    assert not grant(pb, 3), "Rift Glass said WILL+1 but does not raise the cap"
    assert cap(pb) == before == 4
    pb.stop(save=False)
    print("[will-cap-notice] PASS digit starts at 0 with cap 1; Glove, Raft "
          "and Hook each say WILL+1 (cap 4); Glass stays quiet; manual agrees")


if __name__ == "__main__":
    main()
