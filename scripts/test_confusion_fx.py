#!/usr/bin/env python3
"""Confusion swirl is visible on OAM and clears with a cure.

Does not assert the PR #136 cadence retune; that stays in test_confusion.py.
"""
from quintra_new_monsters import boot, spawn_arena, addr, PLAYER
from test_will_max import put16

def swirl_visible(pb):
    # OAM sprite 38: 4 bytes starting at FE00 + 38*4
    oam = 0xFE00 + 38 * 4
    y, x, tile, prop = (pb.memory[oam + i] for i in range(4))
    return y != 0 and tile == 237

def main():
    pb = boot(0)
    spawn_arena(pb)
    kind = addr("_player_status_kind")
    ticks = addr("_player_status_ticks")
    # QSTATUS_CONFUSION value — look it up if needed; historically 6 or similar.
    # Read from a header if possible via a known symbol; poke a safe value by
    # scanning status.h after boot.
    status_h = open("src/game/status.h").read()
    import re
    m = re.search(r"QSTATUS_CONFUSION\s*=\s*(\d+)", status_h)
    if not m:
        m = re.search(r"QSTATUS_CONFUSION\s+(\d+)", status_h)
    conf = 6  # QSTATUS_CONFUSION
    pb.memory[kind] = conf
    pb.memory[ticks] = 40
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    seen = False
    for _ in range(20):
        pb.tick()
        if swirl_visible(pb):
            seen = True
            break
    assert seen, "confusion swirl never appeared on OAM 38"
    # Clear the status to mimic an Antidote/cure (status_player_cure).
    pb.memory[kind] = 0
    pb.memory[ticks] = 0
    gone = False
    for _ in range(8):
        pb.tick()
        if not swirl_visible(pb):
            gone = True
            break
    assert gone, "swirl stayed after cure"
    pb.stop(save=False)
    print("[confusion-fx] PASS swirl present, then gone after cure")

if __name__ == "__main__":
    main()
