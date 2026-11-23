#!/usr/bin/env python3
"""DISARM blocks only the A button; movement and B stay free."""

from test_will_max import (
    PLAYER, boot, clear_arena, player_shots, put16, addr, press,
)

QSTATUS_NONE = 0
QSTATUS_DISARM = 14
WILL_MAX = 180
ENTITY_SIZE = 28

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
    pb.tick(4)
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
    pb = boot(3)  # Picsean: B is a readable shield / signature
    try:
        clear_arena(pb)
        pb.memory[RUN_STATE + DIFFICULTY_OFF] = DIFFICULTY_NORMAL
        kind, ticks = apply_status(pb, QSTATUS_DISARM)
        assert kind == QSTATUS_DISARM, f"DISARM did not land: kind={kind}"
        # Duration counts down every 8 frames; 4 ticks of apply may have
        # consumed one beat, so accept 29 or 30.
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
