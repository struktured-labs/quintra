#!/usr/bin/env python3
"""Record a 4x GIF of the Bubble: flash, contact DISARM, unkillable shot bounce."""
import os
from pathlib import Path
from PIL import Image
from pyboy import PyBoy
from quintra_vignettes import mute_after_class_select
from test_will_max import PLAYER, ENTITIES, SCREEN, ROM, TILEMAP, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y, clear_arena, addr, press, put16

OUT = Path(os.environ.get("QUINTRA_GIF_OUT", "/tmp/quintra-bubble-gifs"))
OUT.mkdir(parents=True, exist_ok=True)

TITLE, CLASS_SELECT, INTRO, ROOM = 1, 2, 4, 5

FRAME = addr("_loop_frame_counter")


def frame_counter(pb):
    return pb.memory[FRAME] | (pb.memory[FRAME + 1] << 8)


def wait_room_live(pb, limit=1800):
    """room_enter sets SCREEN_ROOM before it finishes; wait for loop_run."""
    last = frame_counter(pb)
    for i in range(limit):
        pb.tick()
        now = frame_counter(pb)
        if now != last:
            for _ in range(30):
                pb.tick()
            return i
    raise AssertionError("room_enter never returned to loop_run")

ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE, EF_ALIVE = 0x01, 0x02
ENEMY_BUBBLE = 44
ENEMY_AUX_BUBBLE_IMMORTAL = 0xB7
SPR_ENEMY_BUBBLE = 78
SKULL = bytes([
    0x3C, 0x00, 0x7E, 0x30, 0x7E, 0x20, 0xDB, 0x00,
    0xDB, 0x00, 0x7E, 0x00, 0x3C, 0x00, 0x24, 0x00,
])
# OBJ tile 78 lives at 0x8000 + 78*16
TILE_ADDR = 0x8000 + SPR_ENEMY_BUBBLE * 16


def until_screen(pb, value, limit):
    for i in range(limit):
        if pb.memory[SCREEN] == value:
            return i
        pb.tick()
    return -1 if pb.memory[SCREEN] != value else limit


def boot_room(class_id=0):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    if until_screen(pb, INTRO, 600) < 0 and pb.memory[SCREEN] != TITLE:
        raise AssertionError(f"no intro/title, screen={pb.memory[SCREEN]}")
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, TITLE, 2400) >= 0
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, CLASS_SELECT, 400) >= 0
    pb.tick(20)
    for _ in range(class_id):
        press(pb, "down", held=3, released=6)
    press(pb, "a")
    mute_after_class_select(pb, ROM, settle=30)
    assert until_screen(pb, ROOM, 400) >= 0
    wait_room_live(pb)
    return pb


def load_skull(pb):
    for i, b in enumerate(SKULL):
        pb.memory[TILE_ADDR + i] = b


def poke_bubble(pb, slot, x, y, immortal=False):
    ep = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[ep + i] = 0
    pb.memory[ep + 0] = ENT_ENEMY
    pb.memory[ep + 1] = EF_ACTIVE | EF_ALIVE
    put16(pb, ep + 3, x)
    put16(pb, ep + 7, y)
    pb.memory[ep + 12] = SPR_ENEMY_BUBBLE
    pb.memory[ep + 13] = 0
    pb.memory[ep + 14] = 6
    pb.memory[ep + 15] = 1  # NE diagonal
    pb.memory[ep + 17] = ENEMY_BUBBLE
    pb.memory[ep + 19] = ENEMY_AUX_BUBBLE_IMMORTAL if immortal else 0
    pb.memory[ep + 25] = (6 << 4) | 6
    pb.memory[ep + 26] = 1
    return ep


def grab(pb, scale=4):
    im = pb.screen.image.convert("RGB")
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    return im


def save_gif(name, frames, duration=80):
    path = OUT / name
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=False)
    print("wrote", path, "frames", len(frames), "bytes", path.stat().st_size)


def main():
    pb = boot_room(0)
    clear_arena(pb)
    load_skull(pb)
    # Player mid-left, killable Bubble mid, unkillable one on the right.
    put16(pb, PLAYER + 9, 48)
    put16(pb, PLAYER + 11, 72)
    poke_bubble(pb, 0, 80, 56, immortal=False)
    poke_bubble(pb, 1, 120, 80, immortal=True)
    frames = []
    # Drift and flash.
    for i in range(90):
        pb.tick()
        if i % 2 == 0:
            frames.append(grab(pb))
        if i == 10:
            load_skull(pb)  # in case a room reload overwrote VRAM
    # Walk into the killable Bubble so DISARM lands, then fire A (should fail)
    # and B is unused; keep walking and shooting to show the bounce on the
    # unkillable one.
    pb.button_press("right")
    for i in range(80):
        if i == 20:
            pb.button_press("a")
        if i == 30:
            pb.button_release("a")
        if i == 50:
            pb.button_press("a")
        if i == 60:
            pb.button_release("a")
        pb.tick()
        if i % 2 == 0:
            frames.append(grab(pb))
    pb.button_release("right")
    for i in range(40):
        pb.tick()
        if i % 2 == 0:
            frames.append(grab(pb))
    save_gif("bubble-in-action-4x.gif", frames, duration=80)
    pb.stop(save=False)


if __name__ == "__main__":
    main()
