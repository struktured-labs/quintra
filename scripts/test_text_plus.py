#!/usr/bin/env python3
"""The text screens can draw '+' (#280).

GBDK's font_min has no '+', so "SEL+B" printed as "SEL B" on the Pack and
Waygear pages, and "A+B OATH", "RED ORB + A" and "ORB + A" lost theirs on
the help page. text_putc() now draws '+' from a scratch BG tile.

  * Each of those five places shows the plus glyph, not a blank.
  * The scratch tile is a shop-offer HUD glyph; back in the room it holds
    its HUD art again.
"""
from test_convergence_transform import addr, boot

SCREEN = addr("_loop_current_screen")
SCREEN_ROOM = 5
PLUS_TILE = 40                    # TEXT_PLUS_TILE = HUD_OFFER_HEAL
PLUS = bytes((0x00, 0x00, 0x18, 0x18, 0x18, 0x18, 0x7E, 0x7E,
              0x7E, 0x7E, 0x18, 0x18, 0x18, 0x18, 0x00, 0x00))
# SELECT presses from the first Pack page -> where a '+' must be.
PAGES = {
    0: ("Pack: A TOOL  SEL+B KIT", [(12, 17)]),
    2: ("Waygear: GLASS: SEL+B SHIFT", [(11, 7)]),
    4: ("Help: RED ORB + A, A+B OATH, ORB + A", [(9, 3), (2, 9), (14, 14)]),
}


def tile_data(pb, tile):
    return bytes(pb.memory[0, 0x9000 + tile * 16 + i] for i in range(16))


def plus_cells(pb):
    return [(x, y) for y in range(18) for x in range(20)
            if pb.memory[0, 0x9800 + y * 32 + x] == PLUS_TILE]


def main():
    pb = boot(0)
    pb.tick(30)
    hud_art = tile_data(pb, PLUS_TILE)
    assert hud_art != PLUS

    pb.button("start")
    pb.tick(60)
    for page in range(5):
        if page:
            pb.button("select")
            pb.tick(60)
        if page not in PAGES:
            continue
        name, want = PAGES[page]
        assert plus_cells(pb) == want, (
            f"{name}: '+' at {plus_cells(pb)}, want {want}")
        assert tile_data(pb, PLUS_TILE) == PLUS, f"{name}: '+' glyph is wrong"

    pb.button("start")
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    assert pb.memory[SCREEN] == SCREEN_ROOM, "could not return to the room"
    pb.tick(60)
    assert tile_data(pb, PLUS_TILE) == hud_art, (
        "the '+' scratch tile was not restored to its HUD glyph in play")
    pb.stop(save=False)
    print("[text-plus] PASS '+' drawn on the Pack, Waygear and Help pages "
          "(5 places); scratch tile restored in play")


if __name__ == "__main__":
    main()
