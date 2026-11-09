#!/usr/bin/env python3
"""Live-ROM contract for Toxic Mire's expanding BG body and OBJ heart."""
from pathlib import Path

from test_boss_identity import EN, PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
ENTITY_SIZE = 28
BODY_MIN, BODY_MAX = 55, 63
CAMERA_X = addr("_room_camera_x")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def footprint(body):
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def tick_until_phase(pb, boss, phase):
    for _ in range(8):
        pb.tick()
        if (pb.memory[boss + 15] & 1) == phase:
            body = body_tiles(pb)
            expected = 84 if phase else 36
            if len(body) == expected:
                return body
    raise AssertionError(
        f"Mire never rendered phase {phase}: state={pb.memory[boss + 15]}, "
        f"tiles={len(body_tiles(pb))}")


def main():
    pb, boss = enter_boss(4, keep_open=True)

    # The detached mural is gone. Tiles 55..63 stay off the logical map so the
    # root overlay can reuse their VRAM without becoming terrain.
    assert body_tiles(pb) == [], (
        f"Mire map still paints colossus slots: {body_tiles(pb)[:6]}")

    # The only physical boss body is the OBJ heart. Floor under it stays
    # walkable, including while a root cast may be on the BG.
    put16(pb, PL + 9, 32)
    put16(pb, PL + 11, 32)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    # Consume the queued release before the next direct checkpoint warp.
    # PyBoy 2.7 restores the pre-event CPU sample on this boundary, which can
    # otherwise overwrite a WRAM position written in the same host interval.
    pb.tick()
    assert pb.memory[PL + 9] > before_x, "Mire projection became invisible collision"

    # The huge body now changes footprint inside a true scrolling field.
    # Traverse to the eastern chamber while keeping the WINDOW HUD fixed.
    put16(pb, PL + 9, 200)
    scroll = []
    for _ in range(80):
        pb.tick()
        scroll.append((pb.memory[0xFF43], pb.memory[0xFF42]))
    assert pb.memory[CAMERA_X] == 64 and 61 <= scroll[-1][0] <= 67, (
        f"Mire field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scroll[-1][0]}")
    assert {y for _, y in scroll} == {0}, f"Mire camera tilted: {set(scroll)}"

    image = getattr(pb.screen, "image", None)
    if image is not None:
        image.save(ROOT / "tmp" / "mire-colossal-expanded.png")
    assert body_tiles(pb) == [], "scrolling the arena wrote colossus tiles into the map"
    pb.stop(save=False)

    print("[colossal-mire] PASS slots 55..63 unused on the map; "
          "camera 0..64; floor under the heart stays walkable")


if __name__ == "__main__":
    main()
