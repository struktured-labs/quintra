#!/usr/bin/env python3
"""Live-ROM contract for the BG-body/OBJ-core Void Colossus arena."""
from pathlib import Path

from test_boss_identity import EN, PL, addr, enter_boss, projection_cells, put16


ROOT = Path(__file__).resolve().parent.parent
ENTITY_SIZE = 28
ENT_PROJECTILE = 1
ENT_FX = 4
EYE_TILE = 59
FRAME = addr("_loop_frame_counter")
CAMERA_X = addr("_room_camera_x")


def clear_disposable(pb):
    for index in range(32):
        entity = EN + index * ENTITY_SIZE
        if pb.memory[entity] in (ENT_PROJECTILE, ENT_FX):
            pb.memory[entity] = pb.memory[entity + 1] = 0


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def eye_art_at(frame=None):
    """Sample one blink phase without toggling a live test LCD back on."""
    sample, _ = enter_boss(8, keep_open=True)
    if frame is not None:
        put16(sample, FRAME, frame)
        # enter_boss's VRAM sample briefly toggles LCD off; allow one frame to
        # rejoin VBlank, then cross the authored 0x70 blink boundary.
        for _ in range(4):
            sample.tick()
    lcdc = sample.memory[0xFF40]
    sample.memory[0xFF40] &= 0x7F
    sample.memory[0xFF4F] = 0
    # Quintra uses the signed BG tile-data region (LCDC.4=0); OBJ data at
    # 0x8000 shares numeric tile IDs but is a different address here.
    base = 0x8000 if lcdc & 0x10 else 0x9000
    tile_addr = base + EYE_TILE * 16
    art = bytes(sample.memory[tile_addr:tile_addr + 16])
    observed_frame = sample.memory[FRAME] | sample.memory[FRAME + 1] << 8
    sample.stop(save=False)
    return art, observed_frame


def main():
    pb, boss = enter_boss(8, keep_open=True)
    assert projection_cells(pb) == 0, "Void Lord still paints a detached mural"

    # Projection art is traversable; the 32x32 OBJ core remains the only
    # physical boss body. Walking across a scale tile must not create an
    # invisible wall in the arena.
    clear_disposable(pb)
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 80)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "astral BG body became invisible collision"

    # Every resolved final-boss beat moves the weak point to another authored
    # face/maw anchor instead of letting a tiny sprite creep independently of
    # its screen-scale body.
    before = position(pb, boss)
    pb.memory[boss + 16] = 35
    for _ in range(6):
        pb.tick()
        if position(pb, boss) != before:
            break
    after = position(pb, boss)
    anchors = {(40, 32), (104, 32), (160, 64), (104, 40)}
    assert after in anchors and after != before, f"weak point did not jump anchors: {before}->{after}"

    # World Collapse now marks the same safe corner used by its resolution.
    clear_disposable(pb)
    pb.memory[boss + 21] = 1       # charge active
    pb.memory[boss + 22] = 0       # top-left safe pocket
    pb.memory[boss + 18] = 17      # marker as countdown reaches 16 or 8
    marker = False
    trace = []
    for _ in range(12):
        pb.tick()
        trace.append((pb.memory[boss + 18], pb.memory[boss + 21]))
        for index in range(32):
            entity = EN + index * ENTITY_SIZE
            if pb.memory[entity] == ENT_FX and position(pb, entity) == (20, 20):
                marker = True
                break
        if marker:
            break
    assert marker, ("World Collapse charge did not visibly mark its safe corner; "
                    f"timer={pb.memory[boss + 18]} charge={pb.memory[boss + 21]} "
                    f"slot={pb.memory[boss + 22]} trace={trace}")

    # The shared eye tile blinks and the final arena reaches the eastern
    # chamber without moving the fixed WINDOW HUD.
    (eye_open, open_frame) = eye_art_at(0x7F)
    (eye_closed, closed_frame) = eye_art_at(0x6F)
    assert eye_open == eye_closed and any(eye_open), (
        "Retired Void mural blinked, or its eye tile was not uploaded; "
        f"frames={open_frame}/{closed_frame}")
    put16(pb, PL + 9, 200)
    for _ in range(80):
        pb.tick()
    assert pb.memory[CAMERA_X] == 64 and 61 <= pb.memory[0xFF43] <= 67, (
        f"Void field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={pb.memory[0xFF43]}")

    screenshot = ROOT / "tmp" / "void-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)
    print(f"[colossal-void] PASS no mural, anchor {before}->{after}, "
          f"marked Collapse pocket, static eye atlas")


if __name__ == "__main__":
    main()
