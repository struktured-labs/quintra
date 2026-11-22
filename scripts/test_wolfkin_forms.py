#!/usr/bin/env python3
"""ROM contract: Wolfkin A is a parented longsword, slash vs stab."""
from test_will_max import PLAYER, ENTITIES, boot, clear_arena, put16, addr

ENTITY_SIZE = 28
AUX_FANG = 0xF1


def shots(pb):
    return [ENTITIES + i * ENTITY_SIZE for i in range(32)
            if pb.memory[ENTITIES + i * ENTITY_SIZE] == 1
            and (pb.memory[ENTITIES + i * ENTITY_SIZE + 1] & 0x10)
            and pb.memory[ENTITIES + i * ENTITY_SIZE + 23] == AUX_FANG]


def get16(pb, a):
    v = pb.memory[a] | (pb.memory[a + 1] << 8)
    return v if v < 0x8000 else v - 0x10000


def drop_hp(pb):
    pb.memory[PLAYER + 2] = max(1, pb.memory[PLAYER + 1] - 1)


def main():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb)
        assert pb.memory[PLAYER] == 0

        pb.memory[PLAYER + 22] = 0
        try:
            pb.memory[addr("_player_aim_dir")] = 2
        except RuntimeError:
            pass
        pb.memory[PLAYER + 13] = 1
        origin_x = get16(pb, PLAYER + 9)
        pb.button_press("right")
        pb.button("a")
        for _ in range(4):
            pb.tick()
        pb.button_release("right")
        stab = shots(pb)
        assert stab, "directed A spawned no sword"
        for e in stab:
            assert pb.memory[e + 10] == 0 and pb.memory[e + 11] == 0, "stab travels"
            assert 144 <= pb.memory[e + 12] <= 159, "stab lost Claw Sword art"
            assert pb.memory[e + 16] <= 10, "stab lives too long"
            assert pb.memory[e + 26] == 9, f"stab damage {pb.memory[e + 26]} != 9"
        furthest = max(get16(pb, e + 3) for e in stab)
        for _ in range(10):
            pb.tick()
            live = shots(pb)
            if live:
                furthest = max(furthest, max(get16(pb, e + 3) for e in live))
        assert furthest >= origin_x + 16 + 24, (
            f"stab did not extend to ~32px: origin={origin_x} furthest={furthest}")

        clear_arena(pb)
        drop_hp(pb)
        pb.memory[PLAYER + 22] = 0
        try:
            pb.memory[addr("_player_aim_dir")] = 2
        except RuntimeError:
            pass
        pb.button("a")
        for _ in range(4):
            pb.tick()
        sweep = shots(pb)
        assert sweep, "neutral A spawned no slash"
        assert all(pb.memory[e + 26] == 5 for e in sweep), "slash damage not 5"
        assert all(pb.memory[e + 10] == 0 and pb.memory[e + 11] == 0 for e in sweep)

        combo = boot(0)
        try:
            clear_arena(combo)
            drop_hp(combo)
            combo.memory[PLAYER + 22] = 0
            combo.button_press("left")
            combo.button_press("a")
            seen = 0
            traveling = 0
            for _ in range(72):
                combo.tick()
                for e in shots(combo):
                    seen += 1
                    if combo.memory[e + 10] or combo.memory[e + 11]:
                        traveling += 1
            combo.button_release("a")
            combo.button_release("left")
            assert seen, "held Wolfkin A did not continue the combo"
            assert traveling == 0, "held combo became a traveling shot stream"
        finally:
            combo.stop(save=False)

        hit = boot(0)
        try:
            clear_arena(hit)
            drop_hp(hit)
            hit.memory[PLAYER + 22] = 0
            hit.memory[PLAYER + 13] = 1
            try:
                hit.memory[addr("_player_aim_dir")] = 2
            except RuntimeError:
                pass
            put16(hit, PLAYER + 9, 80)
            put16(hit, PLAYER + 11, 72)
            hit.button_press("right")
            hit.button("a")
            for _ in range(3):
                hit.tick()
            hit.button_release("right")
            hit.button_release("a")
            live = shots(hit)
            assert live, "no stab to test cleave"
            sx = get16(hit, live[0] + 3)
            sy = get16(hit, live[0] + 7)
            foe = next(ENTITIES + i * ENTITY_SIZE for i in range(32)
                       if ENTITIES + i * ENTITY_SIZE not in live
                       and hit.memory[ENTITIES + i * ENTITY_SIZE] == 0)
            for k in range(ENTITY_SIZE):
                hit.memory[foe + k] = 0
            hit.memory[foe] = 2
            hit.memory[foe + 1] = 0x07
            put16(hit, foe + 3, sx)
            put16(hit, foe + 7, sy)
            hit.memory[foe + 14] = 20
            hit.memory[foe + 17] = 2
            hit.memory[foe + 25] = 0x88
            hit.memory[foe + 26] = 1
            # Game logic can lag a video frame; allow up to 3 for contact.
            for _ in range(3):
                hit.tick()
                if hit.memory[foe + 14] != 20:
                    break
            after = hit.memory[foe + 14]
            assert after == 11, f"stab contact was not 9 damage: hp {after}"
            hit.tick()
            assert hit.memory[foe + 14] == after, "one swing damaged the same body twice"
        finally:
            hit.stop(save=False)

        swap = boot(0)
        try:
            clear_arena(swap)
            drop_hp(swap)
            swap.memory[PLAYER + 21] = 1  # Tail Spike item index
            swap.memory[PLAYER + 22] = 0
            swap.button_press("right")
            swap.button("a")
            for _ in range(3):
                swap.tick()
            swap.button_release("right")
            swapped = [ENTITIES + i * ENTITY_SIZE for i in range(32)
                       if swap.memory[ENTITIES + i * ENTITY_SIZE] == 1
                       and (swap.memory[ENTITIES + i * ENTITY_SIZE + 1] & 0x10)]
            assert len(swapped) == 1, f"Tail Spike swap spawned {len(swapped)}"
            assert swap.memory[swapped[0] + 16] > 8, "swap kept the short sword life"
            assert swap.memory[swapped[0] + 25] == 0x77, "swap kept the sword hitbox"
        finally:
            swap.stop(save=False)
    finally:
        pb.stop(save=False)
    print("[wolfkin-forms] PASS parented Claw Sword spin/stab, latch, weapon swap")


if __name__ == "__main__":
    main()
