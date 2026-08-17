#!/usr/bin/env python3
"""Live-ROM contract: Pack-selected physical tools consume and alter rooms."""

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


PLAYER, ENTITIES, SCREEN, TILEMAP, FRAME = map(
    addr, ("_player", "_entities", "_loop_current_screen", "_room_tilemap",
           "_loop_frame_counter"))


def frame_counter(pb):
    return pb.memory[FRAME] | (pb.memory[FRAME + 1] << 8)


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


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0


def set_hostile_shot(pb, vx=2):
    e = ENTITIES
    pb.memory[e] = 1
    pb.memory[e + 1] = 3
    pb.memory[e + 3] = 80
    pb.memory[e + 7] = 64
    pb.memory[e + 11] = vx & 0xFF
    pb.memory[e + 12] = 28
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 80
    pb.memory[e + 25] = 0x55
    pb.memory[e + 26] = 2
    return e


def use_tool(pb, tool_index, item_id):
    pb.memory[PLAYER + 24] = item_id
    press(pb, "start")
    assert pb.memory[SCREEN] == 9, "START did not open Pack"
    # SCREEN changes before the banked Pack renderer finishes. Wait for the
    # dispatcher to complete that loop turn so the following A edge is polled
    # by inventory_tick rather than arriving during its VRAM setup.
    previous_frame = frame_counter(pb)
    for _ in range(240):
        if frame_counter(pb) != previous_frame:
            break
        pb.tick()
    assert frame_counter(pb) != previous_frame, "Pack renderer did not settle"
    for _ in range(tool_index):
        press(pb, "right")
    # Observe the complete Pack->room transaction. Bomb lanes are deliberately
    # brief and can expire before a fixed post-resume sample on a fast host;
    # their peak simultaneous geometry is the actual contract.
    peak_player_shots = 0
    resume_frame = None
    pb.button_press("a")
    for frame in range(240):
        pb.tick()
        if frame == 4:
            pb.button_release("a")
        peak_player_shots = max(peak_player_shots, sum(
            pb.memory[ENTITIES + i * 28] == 1
            and (pb.memory[ENTITIES + i * 28 + 1] & 0x10)
            for i in range(32)))
        if pb.memory[SCREEN] == 5 and resume_frame is None:
            resume_frame = frame_counter(pb)
        elif resume_frame is not None and frame_counter(pb) != resume_frame:
            break
    pb.button_release("a")
    assert pb.memory[SCREEN] == 5, \
        f"tool did not return to room (screen={pb.memory[SCREEN]})"
    assert pb.memory[PLAYER + 24] == 0xFF, "tool charge was not consumed"
    return peak_player_shots


def main():
    # Bomb breaks nearby authored cover and produces a radial attack.
    pb = boot()
    clear_entities(pb)
    # Isolate the Bomb's radial geometry from the opening room's generated
    # pillars.  Terrain destruction is still exercised by the explicit pot.
    for i in range(20 * 17):
        pb.memory[TILEMAP + i] = 1
    pb.memory[PLAYER + 9] = 80
    pb.memory[PLAYER + 10] = 0
    pb.memory[PLAYER + 11] = 64
    pb.memory[PLAYER + 12] = 0
    pb.memory[TILEMAP + 8 * 20 + 11] = 32  # BGT_POT within three tiles
    player_shots = use_tool(pb, 0, 40)
    assert pb.memory[TILEMAP + 8 * 20 + 11] == 1, "Rift Bomb did not break pot"
    assert player_shots >= 4, (
        f"Rift Bomb did not create radial combat pressure: shots={player_shots}"
    )
    pb.stop(save=False)

    # Chime silences a live hostile pattern.
    pb = boot()
    clear_entities(pb)
    shot = set_hostile_shot(pb)
    use_tool(pb, 1, 41)
    assert not (pb.memory[shot + 1] & 1), "Echo Chime left hostile shot active"
    pb.stop(save=False)

    # Mirror turns ownership and velocity back toward the firing side.
    pb = boot()
    clear_entities(pb)
    shot = set_hostile_shot(pb, vx=2)
    use_tool(pb, 2, 42)
    assert pb.memory[shot + 1] & 0x10, "Mirror Shard did not change ownership"
    assert pb.memory[shot + 11] == 0xFE, "Mirror Shard did not reverse velocity"
    assert pb.memory[shot + 26] == pb.memory[PLAYER + 5] + 3
    pb.stop(save=False)
    print("[dungeon-tools] PASS Bomb, Chime, and Mirror physical charges")


if __name__ == "__main__":
    main()
