#!/usr/bin/env python3
"""Live-ROM contract for colored pickup and condition HUD callouts."""

from test_performance import EN, PL, boot_room, put32


WIN = 0x9C00
VBK = 0xFF4F
HUD_BLANK = 8
DIGIT_1 = 10
A, T, K = 84, 79, 88
D, E, F = 82, 86, 78
L, C = 81, 94
H, S = 92, 93
R, G, N = 76, 85, 91
P = 90
PLUS = 95


def clear_entities(pb):
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = 0
        pb.memory[ep + 1] = 0


def spawn_pickup(pb, kind, payload=0):
    ep = EN
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    pb.memory[ep] = 3
    pb.memory[ep + 1] = 0x03
    put32(pb, ep + 2, px << 8)
    put32(pb, ep + 6, py << 8)
    pb.memory[ep + 12] = 35
    pb.memory[ep + 13] = 5
    pb.memory[ep + 14] = 1
    pb.memory[ep + 15] = 0
    pb.memory[ep + 16] = 200
    pb.memory[ep + 17] = kind
    pb.memory[ep + 18] = payload
    pb.memory[ep + 25] = 0x66


def hud_row(pb):
    tiles = tuple(pb.memory[WIN + x] for x in range(10, 16))
    pb.memory[VBK] = 1
    attrs = tuple(pb.memory[WIN + x] & 7 for x in range(10, 16))
    pb.memory[VBK] = 0
    return tiles, attrs


def wait_notice(pb):
    for _ in range(55):
        pb.tick()


def main():
    pb = boot_room()
    try:
        clear_entities(pb)
        # Generated item index 12 is PowerStone: literal red ATK+1.
        spawn_pickup(pb, 3, 12)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert tiles == (A, T, K, PLUS, DIGIT_1, HUD_BLANK), tiles
        assert attrs == (7, 7, 7, 7, 7, 7), attrs
        wait_notice(pb)

        clear_entities(pb)
        # Ward Charm has two effects. DEF+1 displays first; LCK+1 is queued.
        spawn_pickup(pb, 3, 16)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert tiles == (D, E, F, PLUS, DIGIT_1, HUD_BLANK), tiles
        assert attrs == (5, 5, 5, 5, 5, 5), attrs
        for _ in range(45):
            pb.tick()
        tiles, attrs = hud_row(pb)
        assert tiles == (L, C, K, PLUS, DIGIT_1, HUD_BLANK), tiles
        assert attrs == (5, 5, 5, 5, 5, 5), attrs
        wait_notice(pb)

        clear_entities(pb)
        # Temporary Surge applies HASTE and uses the blue magic language.
        spawn_pickup(pb, 14)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert tiles == (H, A, S, T, E, HUD_BLANK), tiles
        assert attrs == (6, 6, 6, 6, 6, 6), attrs
        wait_notice(pb)

        clear_entities(pb)
        # The elder's actual REGEN application exercises green status text.
        spawn_pickup(pb, 7)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert tiles == (R, E, G, E, N, HUD_BLANK), tiles
        assert attrs == (5, 5, 5, 5, 5, 5), attrs
        wait_notice(pb)

        # Hunger lasts across rooms and makes hearts visibly uncollectable;
        # cleansing it restores ordinary pickup behavior immediately.
        clear_entities(pb)
        pb.memory[PL + 46] = 0x08
        pb.memory[PL + 47] = 3
        pb.memory[PL + 2] = pb.memory[PL + 1] - 2
        hp_before = pb.memory[PL + 2]
        spawn_pickup(pb, 0)
        pb.tick()
        assert pb.memory[PL + 2] == hp_before
        assert pb.memory[EN] == 3 and pb.memory[EN + 1] & 1
        pb.memory[PL + 46] = pb.memory[PL + 47] = 0
        pb.tick()
        assert pb.memory[PL + 2] == hp_before + 1
        assert not (pb.memory[EN + 1] & 1)

        # The marked fate orb pulses through its own palette at range, then
        # every possible resolution changes at least one observable run value.
        clear_entities(pb)
        pb.memory[PL + 2] = max(1, pb.memory[PL + 1] - 2)
        pb.memory[PL + 4] = max(0, pb.memory[PL + 3] - 2)
        pb.memory[PL + 5] = min(pb.memory[PL + 5], 12)
        pb.memory[PL + 8] = min(pb.memory[PL + 8], 8)
        pb.memory[PL + 17] = pb.memory[PL + 18] = 0
        spawn_pickup(pb, 24)
        px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
        put32(pb, EN + 2, (px + 32) << 8)
        palettes = set()
        for _ in range(40):
            pb.tick()
            palettes.add(pb.memory[EN + 13] & 7)
        assert {4, 5, 6} <= palettes, palettes
        before = tuple(pb.memory[off] for off in (
            PL + 46, PL + 2, PL + 4, PL + 5, PL + 8, PL + 17, PL + 18))
        put32(pb, EN + 2, px << 8)
        pb.tick()
        after = tuple(pb.memory[off] for off in (
            PL + 46, PL + 2, PL + 4, PL + 5, PL + 8, PL + 17, PL + 18))
        assert after != before, (before, after)
        assert not (pb.memory[EN + 1] & 1)
    finally:
        pb.stop(save=False)

    print("[pickup-feedback] PASS colored gains/status + Hunger heart block + pulsing Wildcard fate")


if __name__ == "__main__":
    main()
