#!/usr/bin/env python3
"""#151 section 3.5: 4-pip mastery strip on the Will window lane."""

from test_will_max import boot, seed_maxwill

HUD_MAXWILL_PIPS = 0xFB
HUD_DIGIT_0 = 9
WIN = 0x9C00

# Packed 2x2 of 3x3 blocks, color 3, L1..L4.
PIP = {
    1: bytes([0x70,0x70, 0x70,0x70, 0x70,0x70, 0,0, 0,0, 0,0, 0,0, 0,0]),
    4: bytes([0x77,0x77, 0x77,0x77, 0x77,0x77, 0,0, 0x77,0x77, 0x77,0x77, 0x77,0x77, 0,0]),
}


def vram_tile(pb, idx):
    pb.memory[0xFF4F] = 0
    base = 0x8000 + idx * 16
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


def pack_resume(pb):
    """Open and close the pack so room_enter runs hud_init / hud_redraw_all."""
    pb.button_press("start")
    pb.tick(10)
    pb.button_release("start")
    pb.tick(6)
    pb.button_press("start")
    pb.tick(10)
    pb.button_release("start")
    pb.tick(10)


def main():
    pb = boot(0)
    check_pips(pb, 1, "boot L1")
    seed_maxwill(pb, 4, 0)
    pack_resume(pb)
    check_pips(pb, 4, "pack resume L4")
    pb.stop(save=False)
    print("[will-pips] PASS 4-pip strip: L1 blank-locked, L4 filled, pal 5, Will bar kept")


if __name__ == "__main__":
    main()
