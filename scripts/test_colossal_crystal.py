#!/usr/bin/env python3
"""Live-ROM contract for the opening Crystal Colossus BG body/OBJ heart."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
FRAME = addr("_loop_frame_counter")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def bg_tile_art(pb, tile):
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    return bytes(pb.memory[base + tile * 16:base + (tile + 1) * 16])


def main():
    pb, boss = enter_boss(0, keep_open=True)
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 110, f"opening Colossus body drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 9), (
        f"opening Colossus lost its 112x72 footprint: "
        f"x={min(xs)}..{max(xs)} y={min(ys)}..{max(ys)}")

    # The enormous statue is projection art; only the original 32x32 heart is
    # physical. Crossing its outer shoulder cannot create an invisible wall.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 24)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Crystal projection became collision"

    # Its Normal pattern and melee accessibility remain the proven classic:
    # the vulnerable heart still pursues the champion rather than camping in
    # a distant decorative socket. The screen-scale projection is spectacle,
    # not a stealth movement or balance rewrite.
    put16(pb, PL + 9, 120)
    put16(pb, PL + 11, 72)
    put16(pb, boss + 3, 64)
    put16(pb, boss + 7, 48)
    pb.memory[boss + 16] = 0
    before = position(pb, boss)
    after = before
    for _ in range(24):
        pb.tick()
        after = position(pb, boss)
        if after != before:
            break
    assert after[0] > before[0] and after[1] >= before[1], (
        f"Crystal heart lost its melee-accessible pursuit: {before}->{after}")

    # The Penta-style moving arena is deliberately sub-tile. It must be
    # unmistakably alive while remaining too small to detach visible walls
    # from their collision cells or move the OBJ weak point/HUD.
    put16(pb, FRAME, 0)
    scx, scy = [], []
    for _ in range(128):
        pb.tick()
        scx.append(pb.memory[0xFF43])
        scy.append(pb.memory[0xFF42])
    assert min(scx) == 0 and max(scx) == 3, \
        f"Crystal moving arena lost its 0..3px orbit: {set(scx)}"
    assert min(scy) == 0 and max(scy) == 1, \
        f"Crystal moving arena lost its 0..1px vertical beat: {set(scy)}"

    screenshot = ROOT / "tmp" / "crystal-colossal-arena.png"
    pb.screen.image.save(screenshot)
    crystal_art = bg_tile_art(pb, BODY_MIN)
    pb.stop(save=False)

    mire, _ = enter_boss(4, keep_open=True)
    mire_art = bg_tile_art(mire, BODY_MIN)
    mire.stop(save=False)
    void, _ = enter_boss(8, keep_open=True)
    void_art = bg_tile_art(void, BODY_MIN)
    void.stop(save=False)
    assert len({crystal_art, mire_art, void_art}) == 3, (
        "Crystal/Mire/Void projections lost their distinct runtime BG art")

    print(f"[colossal-crystal] PASS {len(body)} BG tiles, 112x72 body, "
          f"heart pursuit {before}->{after}, 0..3px moving arena, walkable, "
          f"art distinct from Mire/Void")


if __name__ == "__main__":
    main()
