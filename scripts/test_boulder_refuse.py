#!/usr/bin/env python3
"""Blocked rune boulders play SFX_REFUSE once per room on the first bump."""

from pathlib import Path

from pyboy import PyBoy
from quintra_vignettes import mute_after_class_select
from test_will_max import PLAYER, TILEMAP, SCREEN, ROM, clear_arena, press
from test_will_sfx import sfx_ids
from test_overworld import addr


ROOT = Path(__file__).resolve().parent.parent
ROOM_W = 20
BGT_GATE_BOULDER = 100
FACE_E = 1
WAYGEAR_OWNED = 44
TITLE = 1
CLASS_SELECT = 2
INTRO = 4
ROOM = 5


def structural_contract():
    src = (ROOT / "src/render/gate_boulder.c").read_text()
    header = (ROOT / "src/render/gate_boulder.h").read_text()
    room = (ROOT / "src/game/room.c").read_text()
    assert "sfx_play(SFX_REFUSE);" in src
    assert "s_blocked_done" in src
    assert "if (s_blocked_done || !moving) return;" in src
    assert "void gate_boulder_tick(u8 moving) BANKED;" in header
    assert "gate_boulder_tick((u8)(keys & (J_LEFT | J_RIGHT | J_UP | J_DOWN)));" in room
    # The blocked cue must not share the passable shimmer flag, so a mid-room
    # Glove grant can still shimmer after a first bump.
    assert src.index("s_blocked_done") != src.index("s_cue_done")


def until_screen(pb, value, limit):
    for i in range(limit):
        if pb.memory[SCREEN] == value:
            return i
        pb.tick()
    return -1 if pb.memory[SCREEN] != value else limit


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


def boot(class_id):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    assert until_screen(pb, INTRO, 600) >= 0, "did not reach the intro"
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, TITLE, 2400) >= 0, "did not reach the title"
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, CLASS_SELECT, 200) >= 0, "did not reach class select"
    pb.tick(30)
    for _ in range(class_id):
        press(pb, "down")
        pb.tick(6)
    press(pb, "a")
    mute_after_class_select(pb, ROM, settle=30)
    assert until_screen(pb, ROOM, 400) >= 0, (
        "did not reach the first room", pb.memory[SCREEN])
    wait_room_live(pb)
    assert pb.memory[PLAYER] == class_id
    return pb


def hook_sfx(pb):
    seen = []
    entry = addr("_sfx_play")

    def on_sfx(_ctx):
        seen.append(pb.register_file.A)

    pb.hook_register(entry >> 16, entry & 0xFFFF, on_sfx, None)
    return seen


def place_blocked_boulder(pb):
    clear_arena(pb)
    pb.memory[PLAYER + WAYGEAR_OWNED] = 0
    px, py = 80, 72
    pb.memory[PLAYER + 13] = FACE_E
    tx = (px + 16) >> 3
    ty = (py + 8) >> 3
    pb.memory[TILEMAP + ty * ROOM_W + tx] = BGT_GATE_BOULDER
    return tx, ty


def release(pb):
    for button in ("a", "b", "start", "select", "up", "down", "left", "right"):
        pb.button_release(button)


def collect(pb, seen, frames):
    start = len(seen)
    for _ in range(frames):
        pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]
        pb.memory[PLAYER + 15] = 120
        pb.tick()
    return seen[start:]


def session(class_id, expect_refuse):
    refuse_id = sfx_ids()["SFX_REFUSE"]
    pb = boot(class_id)
    try:
        seen = hook_sfx(pb)
        release(pb)
        place_blocked_boulder(pb)
        idle = collect(pb, seen, 20)
        assert refuse_id not in idle, (
            "facing a blocked boulder without a bump played SFX_REFUSE", idle)
        pb.button_press("right")
        first = collect(pb, seen, 16)
        held = collect(pb, seen, 40)
        if expect_refuse:
            assert first.count(refuse_id) == 1, (
                "first blocked bump missed a single SFX_REFUSE", first)
            assert refuse_id not in held, (
                "held push retriggered SFX_REFUSE", held)
        else:
            assert refuse_id not in first and refuse_id not in held, (
                "a passable hero played SFX_REFUSE on the boulder", first, held)
    finally:
        pb.stop(save=False)


def main():
    structural_contract()
    session(0, expect_refuse=True)
    # Sauran walks the boulders without the Glove; no error cue.
    session(1, expect_refuse=False)
    print("[boulder-refuse] PASS SFX_REFUSE once per room on a blocked bump")


if __name__ == "__main__":
    main()
