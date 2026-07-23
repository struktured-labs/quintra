#!/usr/bin/env python3
"""Live-ROM contract for Toxic Mire's expanding BG body and OBJ heart."""
from pathlib import Path

from test_boss_identity import EN, PL, TM, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
ENTITY_SIZE = 28
BODY_MIN, BODY_MAX = 55, 63


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

    # Reconcile to the clenched phase, then force the existing 48-beat motion
    # timer across both transitions. The background silhouette—not a test-only
    # marker—must follow the live boss state.
    pb.memory[boss + 15] = 0
    pb.memory[boss + 10] = 12
    clenched = tick_until_phase(pb, boss, 0)
    assert len(clenched) == 36 and footprint(clenched) == (8, 6), (
        f"Mire clenched body drifted: {len(clenched)} tiles {footprint(clenched)}")

    pb.memory[boss + 10] = 1
    expanded = tick_until_phase(pb, boss, 1)
    assert len(expanded) == 84 and footprint(expanded) == (12, 8), (
        f"Mire expansion lost its 96x64 footprint: "
        f"{len(expanded)} tiles {footprint(expanded)}")

    # Projection tiles remain walkable. The only physical/vulnerable boss body
    # is still the 32x32 OBJ heart, so the spectacle cannot create invisible
    # collision across the expanded shape.
    put16(pb, PL + 9, 32)
    put16(pb, PL + 11, 32)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Mire projection became invisible collision"

    # The huge body now breathes as an arena as well as changing footprint.
    # Keep the motion bounded below one tile so it cannot alter collision or
    # obscure the fixed WINDOW HUD.
    scroll = []
    for _ in range(160):
        pb.tick()
        scroll.append((pb.memory[0xFF43], pb.memory[0xFF42]))
    assert min(x for x, _ in scroll) == 0 and max(x for x, _ in scroll) == 3, (
        f"Mire camera breath drifted: {set(scroll)}")
    assert {y for _, y in scroll} == {0}, f"Mire camera tilted: {set(scroll)}"

    screenshot = ROOT / "tmp" / "mire-colossal-expanded.png"
    pb.screen.image.save(screenshot)

    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 1
    contracted_again = tick_until_phase(pb, boss, 0)
    assert len(contracted_again) == 36, "Mire did not visibly contract again"
    pb.stop(save=False)

    print("[colossal-mire] PASS 64x48 clenched -> 96x64 expanded -> "
          "64x48 clenched; 0..3px camera breath; BG projection walkable")


if __name__ == "__main__":
    main()
