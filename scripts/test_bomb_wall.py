#!/usr/bin/env python3
"""Live-ROM contract: bomb-only cracked walls open from blasts, not shots or Chime."""

import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

BGT_FLOOR = 1
BGT_DOOR = 3
BGT_WALL_BOMB = 71
ITEM_RIFT_BOMB = 40
ITEM_ECHO_CHIME = 41
ROOM_W = 20
ROOM_H = 17


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(name)
    return int(m.group(1), 16)


PLAYER, ENTITIES, SCREEN, TILEMAP, FRAME, RS = map(
    addr, ("_player", "_entities", "_loop_current_screen", "_room_tilemap",
           "_loop_frame_counter", "_run_state"))

# run_state_t was 70 bytes; bomb_walls_open is the appended u32.
BOMB_WALLS_OPEN = 70


def frame_counter(pb):
    return pb.memory[FRAME] | (pb.memory[FRAME + 1] << 8)


def press(pb, button, held=5, released=6):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot():
    """Power-on to the first room, skipping intro/title/class/vignette."""
    if not ROM.is_file():
        raise SystemExit(f"missing ROM {ROM}")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    # SCREEN_BOOT=0 TITLE=1 CLASS_SELECT=2 INTRO=4 ROOM=5 VIGNETTE=6
    TITLE, CLASS_SELECT, INTRO, ROOM, VIGNETTE = 1, 2, 4, 5, 6

    def screen():
        return pb.memory[SCREEN]

    def wait_for(ids, limit):
        for _ in range(limit):
            if screen() in ids:
                return True
            pb.tick()
        return screen() in ids

    if not wait_for({INTRO, TITLE}, 600):
        raise AssertionError(f"boot never reached intro/title (screen={screen()})")
    if screen() == INTRO:
        pb.tick(30)
        press(pb, "start")
    if not wait_for({TITLE}, 600):
        raise AssertionError(f"boot never reached title (screen={screen()})")
    pb.tick(30)
    press(pb, "start")
    if not wait_for({CLASS_SELECT}, 200):
        raise AssertionError(f"boot never reached class select (screen={screen()})")
    pb.tick(30)
    press(pb, "a")
    if not wait_for({VIGNETTE, ROOM}, 200):
        raise AssertionError(f"boot never left class select (screen={screen()})")
    if not wait_for({ROOM}, 800):
        raise AssertionError(f"boot did not reach room (screen={screen()})")
    pb.tick(30)
    return pb


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0


def flatten_floor(pb):
    for i in range(ROOM_W * ROOM_H):
        pb.memory[TILEMAP + i] = BGT_FLOOR


def tile_at(pb, x, y):
    return pb.memory[TILEMAP + y * ROOM_W + x]


def set_tile(pb, x, y, t):
    pb.memory[TILEMAP + y * ROOM_W + x] = t


def place_player(pb, px, py):
    pb.memory[PLAYER + 9] = px
    pb.memory[PLAYER + 10] = 0
    pb.memory[PLAYER + 11] = py
    pb.memory[PLAYER + 12] = 0


def use_tool(pb, tool_index, item_id):
    pb.memory[PLAYER + 24] = item_id
    press(pb, "start")
    assert pb.memory[SCREEN] == 9, "START did not open Pack"
    previous_frame = frame_counter(pb)
    for _ in range(240):
        if frame_counter(pb) != previous_frame:
            break
        pb.tick()
    assert frame_counter(pb) != previous_frame, "Pack renderer did not settle"
    # Highlight the requested tool slot (0 bomb, 1 chime) then confirm.
    for _ in range(tool_index):
        press(pb, "right")
    resume_frame = None
    pb.button_press("a")
    for frame in range(240):
        pb.tick()
        if frame == 4:
            pb.button_release("a")
        if pb.memory[SCREEN] == 5 and resume_frame is None:
            resume_frame = frame_counter(pb)
        elif resume_frame is not None and frame_counter(pb) != resume_frame:
            break
    pb.button_release("a")
    assert pb.memory[SCREEN] == 5, \
        f"tool did not return to room (screen={pb.memory[SCREEN]})"


def opened_bits(pb):
    v = 0
    for i in range(4):
        v |= pb.memory[RS + BOMB_WALLS_OPEN + i] << (8 * i)
    return v


def main():
    # Rift Bomb opens a bomb-only wall and records the room bit.
    pb = boot()
    pb.tick(240)
    clear_entities(pb)
    flatten_floor(pb)
    # North-edge pair inside the 7x7 window: player (28,19) -> tile (4,3).
    set_tile(pb, 4, 0, BGT_WALL_BOMB)
    set_tile(pb, 5, 0, 2)
    place_player(pb, 28, 19)
    use_tool(pb, 0, ITEM_RIFT_BOMB)
    pb.tick(30)
    assert tile_at(pb, 4, 0) == BGT_DOOR, (
        f"Rift Bomb did not open bomb wall: tile={tile_at(pb, 4, 0)}"
    )
    assert tile_at(pb, 5, 0) == BGT_DOOR, (
        f"Rift Bomb did not open the pair: tile={tile_at(pb, 5, 0)}"
    )
    assert opened_bits(pb) != 0, "bomb_walls_open was not set"
    pb.stop(save=False)

    # Echo Chime glints but does not open.
    pb = boot()
    pb.tick(240)
    clear_entities(pb)
    flatten_floor(pb)
    set_tile(pb, 10, 0, BGT_WALL_BOMB)
    place_player(pb, 80, 24)
    use_tool(pb, 1, ITEM_ECHO_CHIME)
    assert tile_at(pb, 10, 0) == BGT_WALL_BOMB, (
        f"Echo Chime opened the bomb wall: tile={tile_at(pb, 10, 0)}"
    )
    assert opened_bits(pb) == 0, "Chime set bomb_walls_open"
    pb.stop(save=False)

    # A player shot dies on the tile and does not open it.
    pb = boot()
    pb.tick(240)
    clear_entities(pb)
    flatten_floor(pb)
    set_tile(pb, 10, 5, BGT_WALL_BOMB)
    place_player(pb, 80, 80)
    # Spawn a player projectile at (80, 64) moving north into the wall.
    e = ENTITIES
    pb.memory[e] = 1            # ENT_PROJECTILE
    pb.memory[e + 1] = 0x11     # EF_ACTIVE | EF_PLAYER_PROJ
    pb.memory[e + 3] = 80       # x
    pb.memory[e + 7] = 56       # y, just below tile (10,5)
    pb.memory[e + 11] = 0       # vx
    pb.memory[e + 12] = 0xFE    # vy = -2
    pb.memory[e + 14] = 1       # damage
    pb.memory[e + 16] = 80
    for _ in range(30):
        pb.tick()
    assert tile_at(pb, 10, 5) == BGT_WALL_BOMB, (
        f"player shot opened the bomb wall: tile={tile_at(pb, 10, 5)}"
    )
    assert opened_bits(pb) == 0, "shot set bomb_walls_open"
    pb.stop(save=False)

    print("[bomb-wall] PASS Rift Bomb opens, Chime and shots do not")


if __name__ == "__main__":
    main()
