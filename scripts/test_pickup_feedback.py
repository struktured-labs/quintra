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
    finally:
        pb.stop(save=False)

    print("[pickup-feedback] PASS literal queued stat gains + colored temporary/status words")


if __name__ == "__main__":
    main()
