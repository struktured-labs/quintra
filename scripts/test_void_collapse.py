#!/usr/bin/env python3
"""Live-ROM regression: Void Lord World Collapse has one real safe pocket."""
from test_boss_identity import EN, PL, enter_boss, put16


ENTITY_SIZE = 28
ENT_PROJECTILE = 1
PLAYER_HP_MAX = PL + 1
PLAYER_HP = PL + 2
PLAYER_IFRAMES = PL + 15
PLAYER_SHIELD = PL + 20

# entity_t offsets, retained deliberately by entity.h for emulator tooling.
BOSS_VOLLEY_TIMER = 18
BOSS_COLLAPSE_CHARGING = 21
BOSS_SAFE_SLOT = 22
BOSS_DAMAGE = 26


def clear_projectiles(pb):
    """Keep this test about the scripted blast, not an older bullet."""
    for index in range(32):
        entity = EN + index * ENTITY_SIZE
        if pb.memory[entity] == ENT_PROJECTILE:
            pb.memory[entity] = pb.memory[entity + 1] = 0


def resolve_collapse(x, y, safe_slot):
    pb, boss = enter_boss(8, keep_open=True)
    clear_projectiles(pb)
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    pb.memory[PLAYER_HP_MAX] = pb.memory[PLAYER_HP] = 20
    pb.memory[PLAYER_IFRAMES] = 0
    pb.memory[PLAYER_SHIELD] = 0

    # Drive the actual charged branch on the next emulated frame. Slot 4 is
    # intentional: the game must wrap it to the same top-left pocket as 0.
    pb.memory[boss + BOSS_VOLLEY_TIMER] = 0
    pb.memory[boss + BOSS_COLLAPSE_CHARGING] = 1
    pb.memory[boss + BOSS_SAFE_SLOT] = safe_slot
    before = pb.memory[PLAYER_HP]
    blast = pb.memory[boss + BOSS_DAMAGE] + 4
    # Boss-entry presentation can own the first frame after the helper gives
    # us the encounter. Wait for the charged branch itself to consume its
    # flag, rather than treating that handoff as a gameplay frame.
    for _ in range(30):
        pb.tick()
        if pb.memory[boss + BOSS_COLLAPSE_CHARGING] == 0:
            break
    after = pb.memory[PLAYER_HP]
    state = (pb.memory[boss + BOSS_VOLLEY_TIMER],
             pb.memory[boss + BOSS_COLLAPSE_CHARGING],
             pb.memory[boss + BOSS_SAFE_SLOT])
    pb.stop(save=False)
    assert state[1] == 0, f"World Collapse did not resolve within 30 frames: {state}"
    return before, after, blast, state


def main():
    safe_before, safe_after, blast, safe_state = resolve_collapse(20, 20, 4)
    unsafe_before, unsafe_after, _, unsafe_state = resolve_collapse(80, 64, 0)
    assert safe_after == safe_before, (
        f"top-left safe pocket took damage ({safe_before}->{safe_after})"
    )
    assert unsafe_after == unsafe_before - blast, (
        f"World Collapse should hit outside its pocket for {blast}; "
        f"got {unsafe_before}->{unsafe_after}; post-state={unsafe_state}, "
        f"safe-state={safe_state}"
    )
    print(f"[void-collapse] PASS slot4 wraps to top-left; safe={safe_after}; "
          f"unsafe blast={blast}")


if __name__ == "__main__":
    main()
