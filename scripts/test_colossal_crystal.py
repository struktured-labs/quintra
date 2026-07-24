#!/usr/bin/env python3
"""Live-ROM contract for Crystal's 224px camera-travelling Colossus arena."""
from pathlib import Path

from test_boss_identity import PL, RS, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
FRAME = addr("_loop_frame_counter")
WORLD_W = addr("_room_world_width")
CAMERA_X = addr("_room_camera_x")


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
    art = bytes(pb.memory[base + tile * 16:base + (tile + 1) * 16])
    pb.memory[0xFF40] = lcdc
    return art


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

    assert pb.memory[WORLD_W] == 224, (
        f"Crystal arena world width drifted: {pb.memory[WORLD_W]}")

    # Column 19 is a real seam, not an invisible old room boundary. Walk the
    # cartridge's normal feet box across x=160 and watch its camera follow.
    put16(pb, PL + 9, 144)
    put16(pb, PL + 11, 96)
    pb.memory[PL + 15] = 255
    pb.button_press("right")
    for _ in range(40):
        pb.tick()
    pb.button_release("right")
    crossed_x = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
    assert crossed_x > 160, f"old viewport seam still blocked the hero: x={crossed_x}"
    assert 0 < pb.memory[CAMERA_X] <= 64, (
        f"camera did not follow across seam: {pb.memory[CAMERA_X]}")
    assert pb.memory[0xFF43] == pb.memory[CAMERA_X], (
        f"SCX/camera contract diverged: {pb.memory[0xFF43]} != {pb.memory[CAMERA_X]}")

    # The vulnerable core now announces and jumps among three authored wells;
    # one is genuinely beyond the former 160px room. Force the final beat of
    # its public timer and observe ordinary ROM AI perform the warp.
    put16(pb, boss + 3, 96)
    put16(pb, boss + 7, 32)
    pb.memory[boss + 15] = 1       # middle well
    pb.memory[boss + 10] = 1       # vx phase countdown
    before = position(pb, boss)
    for _ in range(2):
        pb.tick()
    after = position(pb, boss)
    assert before == (96, 32) and after == (176, 72), (
        f"Crystal did not warp into the wide well: {before}->{after}")
    assert pb.memory[boss + 18] >= 30, (
        "Crystal warp lost its post-jump attack grace")

    # Driving to the far side must reach the full 64px camera bound without
    # vertical shake detaching the BG from its world collision.
    put16(pb, PL + 9, 200)
    for _ in range(40):
        pb.tick()
    assert pb.memory[CAMERA_X] == 64 and pb.memory[0xFF43] == 64, (
        f"wide camera never reached its far bound: "
        f"state={pb.memory[CAMERA_X]} SCX={pb.memory[0xFF43]}")
    assert pb.memory[0xFF42] == 0, "wide arena introduced vertical map drift"

    screenshot = ROOT / "tmp" / "crystal-colossal-arena.png"
    pb.screen.image.save(screenshot)
    crystal_art = bg_tile_art(pb, BODY_MIN)

    # The extension ends at a physical wall during combat. Once the Colossus
    # is retired, the normal pending-unseal transaction must open the actual
    # x=27 threshold and descend to Riftwild—never the obsolete x=19 seam.
    put16(pb, PL + 9, 200)
    put16(pb, PL + 11, 60)
    pb.button_press("right")
    for _ in range(20):
        pb.tick()
    pb.button_release("right")
    blocked_x = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
    assert blocked_x <= 202 and pb.memory[RS + 17] == 0, (
        f"combat arena leaked through far wall: x={blocked_x}")
    pb.memory[boss] = pb.memory[boss + 1] = 0
    pb.memory[RS + 11] = 1          # defeated opening boss
    pb.memory[RS + 12] = 1          # ordinary pending-unseal transaction
    for _ in range(2):
        pb.tick()
    pb.button_press("right")
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 17] == 1:
            break
    pb.button_release("right")
    assert pb.memory[RS + 17] == 1, (
        "far Crystal threshold did not descend to Riftwild after clear")
    pb.stop(save=False)

    mire, _ = enter_boss(4, keep_open=True)
    assert mire.memory[WORLD_W] == 160 and mire.memory[CAMERA_X] == 0, (
        "wide arena state leaked into an ordinary Colossus room")
    mire_art = bg_tile_art(mire, BODY_MIN)
    mire.stop(save=False)
    void, _ = enter_boss(8, keep_open=True)
    void_art = bg_tile_art(void, BODY_MIN)
    void.stop(save=False)
    assert len({crystal_art, mire_art, void_art}) == 3, (
        "Crystal/Mire/Void projections lost their distinct runtime BG art")

    print(f"[colossal-crystal] PASS {len(body)} BG tiles, 112x72 body, "
          f"224px walkable arena, seam x={crossed_x}, camera 0..64, "
          f"well warp {before}->{after}, art distinct from Mire/Void")


if __name__ == "__main__":
    main()
