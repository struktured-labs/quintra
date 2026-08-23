#!/usr/bin/env python3
"""Live-ROM contracts for Mute and the temporary Rift Inversion trick."""

from test_will_max import (
    PLAYER, boot, clear_arena, player_shots, put16,
)


QSTATUS_NONE = 0
QSTATUS_MUTE = 7
QSTATUS_INVERSION = 13
WILL_MAX = 180


def addr(name):
    from test_will_max import addr as symbol_addr
    return symbol_addr(name)


PLAYER_STATUS = addr("_player_status_kind")
PLAYER_STATUS_TICKS = addr("_player_status_ticks")
TRANSFORM_TICKS = addr("_room_transform_ticks")


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
    pb.memory[PLAYER + 23] = 0  # move accumulator
    pb.tick(16)                 # expire the prior double-tap window


def test_rift_inversion():
    pb = boot(0)
    try:
        clear_arena(pb)
        # ATK is deliberately strongest and SPD weakest. Inversion must make
        # the live movement path read SPD=9 without rewriting either field.
        authored = (9, 3, 1, 5)
        for offset, value in enumerate(authored, start=5):
            pb.memory[PLAYER + offset] = value
        pb.memory[PLAYER_STATUS] = QSTATUS_NONE
        pb.memory[PLAYER_STATUS_TICKS] = 0
        reset_position(pb)
        ordinary = travel_right(pb)

        reset_position(pb)
        pb.memory[PLAYER_STATUS] = QSTATUS_INVERSION
        pb.memory[PLAYER_STATUS_TICKS] = 75
        inverted = travel_right(pb)
        assert inverted >= ordinary + 12, (
            f"Rift Inversion did not swap weak SPD with strong ATK: "
            f"ordinary={ordinary}px inverted={inverted}px"
        )
        assert tuple(pb.memory[PLAYER + i] for i in range(5, 9)) == authored, (
            "Rift Inversion mutated permanent run stats"
        )

        # One remaining eight-frame beat expires back to the untouched build.
        pb.memory[PLAYER_STATUS_TICKS] = 1
        pb.tick(16)
        assert pb.memory[PLAYER_STATUS] == QSTATUS_NONE, (
            "Rift Inversion did not expire cleanly"
        )
        reset_position(pb)
        restored = travel_right(pb)
        assert abs(restored - ordinary) <= 1, (
            f"expired inversion left movement altered: {restored} vs {ordinary}"
        )
    finally:
        pb.stop(save=False)


def test_mute_keeps_body_seals_spirit():
    pb = boot(3)  # Picsean makes the blocked shield/signature easy to observe.
    try:
        clear_arena(pb)
        pb.memory[PLAYER_STATUS] = QSTATUS_MUTE
        pb.memory[PLAYER_STATUS_TICKS] = 75
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]  # full MP
        pb.memory[PLAYER + 19] = 0                    # signature ready
        pb.memory[PLAYER + 20] = 0                    # no existing shield
        pb.memory[PLAYER + 42] = WILL_MAX

        pb.button_press("b")
        pb.tick(4)
        pb.button_release("b")
        pb.tick(4)
        assert pb.memory[PLAYER + 4] == pb.memory[PLAYER + 3], (
            "Mute spent MP on Picsean's sealed B"
        )
        assert pb.memory[PLAYER + 20] == 0, "Mute allowed Undertow"

        # Full Will would normally create Moon Tide. Muted A instead remains
        # the physical/basic one-shot action and preserves the sealed meter.
        pb.button_press("right")
        pb.button_press("a")
        pb.tick(5)
        pb.button_release("a")
        pb.button_release("right")
        pb.tick(2)
        shots = player_shots(pb)
        assert len(shots) == 1, (
            f"Mute should preserve one basic A shot, found {len(shots)}"
        )
        assert pb.memory[PLAYER + 42] == WILL_MAX, "Mute allowed a Will MAX"

        clear_arena(pb)
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
        pb.memory[PLAYER + 19] = 0
        pb.button_press("a")
        pb.button_press("b")
        pb.tick(5)
        pb.button_release("a")
        pb.button_release("b")
        pb.tick(3)
        assert pb.memory[TRANSFORM_TICKS] == 0, (
            "Mute allowed Spirit Convergence"
        )
        assert pb.memory[PLAYER + 4] == pb.memory[PLAYER + 3], (
            "Mute spent MP on sealed Spirit Convergence"
        )
    finally:
        pb.stop(save=False)


def main():
    test_rift_inversion()
    test_mute_keeps_body_seals_spirit()
    print("[status-effects] PASS temporary stat inversion + physical-only Mute")


if __name__ == "__main__":
    main()
