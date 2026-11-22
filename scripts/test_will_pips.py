#!/usr/bin/env python3
"""#151 section 3.5: 4-pip mastery strip on the Will window lane."""

from test_will_max import boot, seed_maxwill
from test_magic import arena, entity, tap, run_until

HUD_MAXWILL_PIPS = 123
HUD_DIGIT_0 = 9
WIN = 0x9C00
HP = 14

# Packed 2x2 of 3x3 blocks, color 3, L1 / L2 / L4.
PIP = {
    1: bytes([0x70,0x70, 0x70,0x70, 0x70,0x70, 0,0, 0,0, 0,0, 0,0, 0,0]),
    2: bytes([0x77,0x77, 0x77,0x77, 0x77,0x77, 0,0, 0,0, 0,0, 0,0, 0,0]),
    4: bytes([0x77,0x77, 0x77,0x77, 0x77,0x77, 0,0, 0x77,0x77, 0x77,0x77, 0x77,0x77, 0,0]),
}


def vram_tile(pb, idx):
    # Window/BG uses 8800 addressing: tiles 0-127 live at 0x9000, 128-255
    # at 0x8800 (which is also 0x8000+idx*16). OBJ 0-127 is 0x8000 and
    # must not be confused with a low HUD tile.
    pb.memory[0xFF4F] = 0
    base = (0x9000 + idx * 16) if idx < 128 else (0x8000 + idx * 16)
    return bytes(pb.memory[base:base + 16])


def win_tile(pb, col):
    pb.memory[0xFF4F] = 0
    return pb.memory[WIN + col]


def win_attr(pb, col):
    pb.memory[0xFF4F] = 1
    attr = pb.memory[WIN + col] & 7
    pb.memory[0xFF4F] = 0
    return attr


def check_pips(pb, lv, label):
    tile = win_tile(pb, 11)
    attr = win_attr(pb, 11)
    data = vram_tile(pb, HUD_MAXWILL_PIPS)
    assert tile == HUD_MAXWILL_PIPS, (
        f"{label}: window col 11 tile {tile}, expected {HUD_MAXWILL_PIPS}")
    assert attr == 5, f"{label}: col 11 pal {attr}, expected Will pal 5"
    assert data == PIP[lv], f"{label}: pip VRAM {data.hex()} != L{lv} {PIP[lv].hex()}"
    # Resource Will digit + 3-segment bar stay in cols 12-15.
    assert HUD_DIGIT_0 <= win_tile(pb, 12) <= HUD_DIGIT_0 + 9, (
        f"{label}: Will digit missing at col 12 ({win_tile(pb, 12)})")


def main():
    pb = boot(0)
    check_pips(pb, 1, "boot L1")

    # Cap-up is the live redraw path (hud_redraw_all / pack resume can
    # reload the last suspend save and would wipe a WRAM-only poke).
    arena(pb, cap=1)
    seed_maxwill(pb, 1, 79)
    foe = entity(pb, 0, 2, 124, 30, hp=1, enemy_id=3)
    tap(pb)
    assert run_until(pb, 90, lambda: pb.memory[foe + HP] == 0), (
        "L1->L2 cap-up kill did not land")
    # Cap-up uploads at the next vblank (wait_vbl_done in the pip writer).
    pb.tick(5)
    check_pips(pb, 2, "cap-up L2")

    arena(pb, cap=3)
    seed_maxwill(pb, 3, 279)
    foe = entity(pb, 0, 2, 124, 30, hp=1, enemy_id=3)
    tap(pb)
    assert run_until(pb, 90, lambda: pb.memory[foe + HP] == 0), (
        "L3->L4 cap-up kill did not land")
    pb.tick(5)
    check_pips(pb, 4, "cap-up L4")

    pb.stop(save=False)
    print("[will-pips] PASS 4-pip strip: L1 boot, cap-up L2 and L4, pal 5, Will bar kept")


if __name__ == "__main__":
    main()
