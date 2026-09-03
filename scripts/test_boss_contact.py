#!/usr/bin/env python3
"""Boss body contact must cost more than the old half-heart positioning tax.

Walks the hero into the serpent's body on Normal and asserts the HP loss
from a single contact tick is at least 2 (computed damage halved, min 1),
and that i-frames were granted so it is one legible hit, not a drain.

The serpent's tail ribbon and volley projectiles have their own separately
authored damage rules, so both are neutralized every frame; only the boss
body's combat_resolve branch can take the HP under test.
"""
from test_boss_identity import EN, PL, addr, enter_boss

# player_state_t layout (src/game/player.h): class_id, hp_max, hp, mp_max,
# mp, atk, def, spd, lck (9 bytes), then x/y as i16 (4 bytes), facing,
# anim_frame, then iframes at offset 15 — the same slot test_boss_identity.py
# holds at 255 to keep its observer invulnerable.
PLAYER_HP_OFFSET = 2
PLAYER_IFRAMES_OFFSET = 15

TAIL_ACTIVE = addr("_serpent_tail_active")


def isolate_boss_body(pb):
    # Tail brushes cost a flat half-heart via serpent_tail_contact and would
    # mask the body rule; volley shots would likewise register first.
    pb.memory[TAIL_ACTIVE] = 0
    for i in range(32):
        ep = EN + i * 28
        if (pb.memory[ep] == 1 and pb.memory[ep + 1] & 1
                and not (pb.memory[ep + 1] & 0x10)):
            pb.memory[ep] = pb.memory[ep + 1] = 0


def main():
    pb, serpent = enter_boss(1, keep_open=True)   # stage-2 serpent
    player_hp = PL + PLAYER_HP_OFFSET
    iframes = PL + PLAYER_IFRAMES_OFFSET
    hp_before = pb.memory[player_hp]
    # Drive the hero straight at the boss body until contact registers,
    # steering along the larger axis gap each beat.
    for _ in range(600):
        px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
        py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
        bx = pb.memory[serpent + 3] | (pb.memory[serpent + 4] << 8)
        by = pb.memory[serpent + 7] | (pb.memory[serpent + 8] << 8)
        dx, dy = bx - px, by - py
        if abs(dy) >= abs(dx):
            button = "down" if dy > 0 else "up"
        else:
            button = "right" if dx > 0 else "left"
        pb.button_press(button)
        for _ in range(3):
            isolate_boss_body(pb)
            pb.tick()
            if pb.memory[player_hp] < hp_before:
                break
        pb.button_release(button)
        if pb.memory[player_hp] < hp_before:
            break
    loss = hp_before - pb.memory[player_hp]
    assert loss >= 2, f"boss contact cost {loss}, expected >= 2 on Normal"
    assert pb.memory[iframes] > 0, "contact granted no i-frames"
    pb.stop(save=False)
    print(f"PASS boss contact loss={loss}")


if __name__ == "__main__":
    main()
