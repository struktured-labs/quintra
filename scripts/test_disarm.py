#!/usr/bin/env python3
"""DISARM blocks only the A button; movement and B stay free."""


from pyboy import PyBoy
from quintra_vignettes import mute_after_class_select
from test_will_max import (
    PLAYER, SCREEN, ROM, clear_arena, player_shots, put16, addr, press,
)

TITLE, CLASS_SELECT, INTRO, ROOM = 1, 2, 4, 5


def until_screen(pb, value, limit):
    for i in range(limit):
        if pb.memory[SCREEN] == value:
            return i
        pb.tick()
    return -1 if pb.memory[SCREEN] != value else limit


def boot_room(class_id):
    """Reach the first room with the foyer vignette muted (not the tight boot())."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    if until_screen(pb, INTRO, 600) < 0 and pb.memory[SCREEN] != TITLE:
        raise AssertionError(f"did not reach intro/title, screen={pb.memory[SCREEN]}")
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, TITLE, 2400) >= 0, f"did not reach title, screen={pb.memory[SCREEN]}"
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, CLASS_SELECT, 400) >= 0, (
        f"did not reach class select, screen={pb.memory[SCREEN]}")
    pb.tick(20)
    for _ in range(class_id):
        press(pb, "down", held=3, released=6)
    press(pb, "a")
    mute_after_class_select(pb, ROM, settle=30)
    assert until_screen(pb, ROOM, 400) >= 0, f"did not reach room, screen={pb.memory[SCREEN]}"
    assert pb.memory[PLAYER] == class_id, f"class {pb.memory[PLAYER]} != {class_id}"
    return pb

QSTATUS_NONE = 0
QSTATUS_DISARM = 14

PLAYER_STATUS = addr("_player_status_kind")
PLAYER_STATUS_TICKS = addr("_player_status_ticks")
STATUS_REQ = addr("_status_apply_req")
RUN_STATE = addr("_run_state")
DIFFICULTY_OFF = 26  # run_state.difficulty
DIFFICULTY_NORMAL, DIFFICULTY_EASY = 0, 1


def apply_status(pb, kind):
    pb.memory[PLAYER_STATUS] = 0
    pb.memory[PLAYER_STATUS_TICKS] = 0
    pb.memory[STATUS_REQ] = kind
    for _ in range(8):
        pb.tick()
        if pb.memory[PLAYER_STATUS] == kind:
            break
    return pb.memory[PLAYER_STATUS], pb.memory[PLAYER_STATUS_TICKS]


def travel_right(pb, frames=16):
    start = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
    pb.button_press("right")
    pb.tick(frames)
    pb.button_release("right")
    pb.tick(2)
    finish = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
    return finish - start


def reset_position(pb):
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 23] = 0
    pb.tick(4)


def test_disarm_blocks_only_a():
    pb = boot_room(3)  # Picsean: B is a readable shield / signature
    try:
        clear_arena(pb)
        pb.memory[RUN_STATE + DIFFICULTY_OFF] = DIFFICULTY_NORMAL
        kind, ticks = apply_status(pb, QSTATUS_DISARM)
        assert kind == QSTATUS_DISARM, f"DISARM did not land: kind={kind}"
        # Duration counts down every 8 frames; apply may have consumed one beat.
        assert 28 <= ticks <= 30, f"Normal DISARM duration drifted: {ticks}"

        reset_position(pb)
        moved = travel_right(pb)
        assert moved >= 8, f"DISARM froze movement: {moved}px"

        clear_arena(pb)
        pb.memory[PLAYER_STATUS] = QSTATUS_DISARM
        pb.memory[PLAYER_STATUS_TICKS] = 30
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]  # full MP
        pb.memory[PLAYER + 19] = 0
        pb.memory[PLAYER + 20] = 0
        pb.memory[PLAYER + 42] = 0  # no Will MAX
        pb.button_press("right")
        pb.button_press("a")
        pb.tick(5)
        pb.button_release("a")
        pb.button_release("right")
        pb.tick(2)
        shots = player_shots(pb)
        assert len(shots) == 0, f"DISARM allowed an A shot: {len(shots)}"

        # B must still work. Picsean's B spends MP or raises a ward.
        mp_before = pb.memory[PLAYER + 4]
        ward_before = pb.memory[PLAYER + 20]
        pb.button_press("b")
        pb.tick(6)
        pb.button_release("b")
        pb.tick(4)
        assert (
            pb.memory[PLAYER + 4] < mp_before
            or pb.memory[PLAYER + 20] != ward_before
        ), "DISARM sealed B as well as A"

        # Easy halves the authored 30-beat timer.
        pb.memory[RUN_STATE + DIFFICULTY_OFF] = DIFFICULTY_EASY
        kind, ticks = apply_status(pb, QSTATUS_DISARM)
        assert kind == QSTATUS_DISARM, "Easy DISARM did not land"
        assert 14 <= ticks <= 16, f"Easy DISARM duration drifted: {ticks}"
    finally:
        pb.stop(save=False)


def main():
    test_disarm_blocks_only_a()
    print("[disarm] PASS A-lock only; movement and B remain; Easy halves duration")


if __name__ == "__main__":
    main()
