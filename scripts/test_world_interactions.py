#!/usr/bin/env python3
"""Live-ROM contract: attacks, hostile fire, and terrain share world rules."""

import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(name)
    return int(m.group(1), 16)


PLAYER, ENTITIES, SCREEN, TILEMAP, RUN, PUZZLE, PHASE_BIT = map(addr, (
    "_player", "_entities", "_loop_current_screen", "_room_tilemap",
    "_run_state", "_room_puzzle_kind", "_room_puzzle_phase_bit"))


def press(pb, button, held=5, released=6):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    press(pb, "a")
    pb.tick(90)
    assert pb.memory[SCREEN] == 5
    return pb


def put16(pb, at, value):
    pb.memory[at] = value & 0xFF
    pb.memory[at + 1] = (value >> 8) & 0xFF


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0


def projectile(pb, slot, player_owned, x, y, damage=2, element=0, physical=0):
    e = ENTITIES + slot * 28
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x13 if player_owned else 0x03
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 10] = 0
    pb.memory[e + 11] = 0
    pb.memory[e + 12] = 28
    pb.memory[e + 14] = 2
    pb.memory[e + 16] = 30
    pb.memory[e + 18] = element
    pb.memory[e + 19] = physical
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = damage
    return e


def terrain_probe(pb, tile, element, expected):
    # Direct WRAM construction can land while the cartridge still has the old
    # slot cached inside a nested update. Retire that frame, then republish the
    # clean table at an ordinary game-loop boundary before installing the
    # synthetic projectile fixture.
    clear_entities(pb)
    pb.tick(4)
    clear_entities(pb)
    tx, ty = 10, 8
    pb.memory[TILEMAP + ty * 20 + tx] = tile
    shot = projectile(pb, 0, True, tx * 8, ty * 8, element=element)
    pb.tick(10)
    assert pb.memory[TILEMAP + ty * 20 + tx] == expected, (
        f"element {element} left tile {tile} unchanged")


def main():
    pb = boot()
    # Fire burns solid trees to searchable rubble; ice bridges spikes.
    terrain_probe(pb, tile=39, element=1, expected=23)
    terrain_probe(pb, tile=31, element=2, expected=19)

    # Lightning throws a phase switch from range and keeps its visible switch.
    clear_entities(pb)
    pb.memory[PUZZLE] = 3
    pb.memory[PHASE_BIT] = 1
    pb.memory[RUN + 28] = 0
    pb.memory[TILEMAP + 8 * 20 + 10] = 33  # BGT_SWITCH
    projectile(pb, 0, True, 80, 64, element=4)
    pb.tick(10)
    assert pb.memory[RUN + 28] & 1, "lightning did not toggle remote phase state"
    # Tile mutation waits for real VBlank.  Let the banked helper return and
    # retire its original slot before reusing slot zero for the next fixture.
    pb.tick(20)

    # Heavy hostile fire destroys its own cover rather than dying harmlessly.
    clear_entities(pb)
    # The preceding remote-switch fixture deliberately leaves the room in a
    # live phase-puzzle mode.  Retire that authored rule before substituting a
    # pot into the same coordinate or the normal puzzle tick may restore the
    # phase tile while this independent interaction is under observation.
    pb.memory[PUZZLE] = 0
    pb.memory[TILEMAP + 8 * 20 + 10] = 32  # BGT_POT
    # Fixtures are injected asynchronously into a running ROM.  If this lands
    # between the room's update and combat phases, do not let the synthetic
    # stationary shot hit the champion before its next terrain update.
    pb.memory[PLAYER + 15] = 60  # player.iframes
    hostile = projectile(pb, 0, False, 80, 64, damage=2)
    pb.tick(10)
    assert pb.memory[TILEMAP + 8 * 20 + 10] == 1, "enemy fire did not break pot"
    assert not (pb.memory[hostile + 1] & 1), "cover-breaking shot stayed alive"

    # A physical A hitbox cuts an overlapping hostile bullet and retains one
    # pierce, giving melee a world-rule defense rather than a bespoke shield.
    clear_entities(pb)
    blade = projectile(pb, 0, True, 72, 64, damage=3, physical=1)
    shot = projectile(pb, 1, False, 72, 64, damage=2)
    pb.tick(8)
    assert not (pb.memory[shot + 1] & 1), "physical strike did not cut hostile shot"
    assert pb.memory[blade + 1] & 1, "two-pierce blade was wrongly consumed"
    assert pb.memory[blade + 14] == 1, "bullet cut did not spend one blade pierce"
    pb.stop(save=False)
    print("[world-interactions] PASS elements, destructive fire, and bullet cutting")


if __name__ == "__main__":
    main()
