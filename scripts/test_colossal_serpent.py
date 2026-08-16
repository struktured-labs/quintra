#!/usr/bin/env python3
"""Live-ROM contract for Verdant's feeding, growth, AOE, and bullet hell."""
from pathlib import Path

from test_boss_identity import EN, PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
RUNE_TILE = 61
FRAME = addr("_loop_frame_counter")
CAMERA_X = addr("_room_camera_x")
ENTITY_SIZE = 28


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def rune_art(frame):
    pb, _ = enter_boss(1, keep_open=True)
    put16(pb, FRAME, frame)
    for _ in range(4):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    art = bytes(pb.memory[base + RUNE_TILE * 16:base + (RUNE_TILE + 1) * 16])
    pb.stop(save=False)
    return art


def main():
    pb, boss = enter_boss(1, keep_open=True)
    # The projected body now grows one visible coil for every storm mote the
    # head eats. Drive all four real feeding resolutions and pin five lengths.
    food = ((184, 24), (28, 92), (176, 96), (44, 28))
    counts = [len(body_tiles(pb))]
    for growth, (food_x, food_y) in enumerate(food):
        # This fixture accelerates four meals while the real rotating cross
        # keeps firing. Keep the observer alive until the later explicit AOE
        # damage probe; otherwise a fully active off-camera Colossus can end
        # the synthetic sequence and the game-over map masquerades as a coil.
        pb.memory[PL + 15] = 255
        put16(pb, boss + 3, food_x - 12)
        put16(pb, boss + 7, food_y - 12)
        pb.memory[boss + 15] = 0
        pb.memory[boss + 16] = 1
        pb.memory[boss + 21] = growth
        for _ in range(30):
            pb.tick()
            if pb.memory[boss + 21] == growth + 1:
                break
        assert pb.memory[boss + 21] == growth + 1, (
            f"Serpent ignored storm mote {growth + 1}: "
            f"state={pb.memory[boss + 15]} timer={pb.memory[boss + 16]} "
            f"growth={pb.memory[boss + 21]} pos={position(pb, boss)} "
            f"flags={pb.memory[boss + 1]:02x}")
        # Growth redraw uploads eight BG rows on successive safe VBlanks. Let
        # that banked transaction return before staging the next synthetic
        # meal; writing the entity halfway through it is not a real gameplay
        # state and can leave the test waiting on the prior call frame.
        settled_frame = pb.memory[FRAME] | pb.memory[FRAME + 1] << 8
        for _ in range(120):
            pb.tick()
            now = pb.memory[FRAME] | pb.memory[FRAME + 1] << 8
            if now != settled_frame:
                break
        assert now != settled_frame, "Serpent growth upload did not return to gameplay"
        counts.append(len(body_tiles(pb)))
    assert counts == [32, 40, 52, 68, 84], (
        f"Serpent did not grow one readable coil per meal: {counts}")
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 8), (
        f"Serpent lost its 112x64 outer span: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert not BODY_MIN <= tiles[7 * 20 + 9] <= BODY_MAX
    assert not BODY_MIN <= tiles[9 * 20 + 10] <= BODY_MAX, (
        "Serpent coil lost its hollow S-shaped waist")

    # Crossing the charged coil must remain possible; only the mobile OBJ
    # head owns the fight's vulnerable/contact body.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Serpent coil became collision"

    # At full length the ordinary rotating four-cross still fires while the
    # close-range blast is charging: gimmick plus bullet hell, not a cutscene.
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 1:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 72
    pb.memory[boss + 18] = 0
    pb.memory[boss + 21] = 4
    hostile = 0
    for _ in range(30):
        pb.tick()
        hostile = sum(pb.memory[EN + i * ENTITY_SIZE] == 1
                      and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
                      and not pb.memory[EN + i * ENTITY_SIZE + 1] & 0x10
                      for i in range(32))
        if hostile:
            break
    assert hostile == 4, f"Serpent charge silenced its bullet hell: {hostile} shots"

    # Resolve the advertised square blast away from contact damage, then pin
    # the shield counterplay and visible contraction beat.
    put16(pb, boss + 3, 80)
    put16(pb, boss + 7, 48)
    put16(pb, PL + 9, 120)
    put16(pb, PL + 11, 48)
    pb.memory[PL + 2] = 10
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 1
    for _ in range(4):
        pb.tick()
        if pb.memory[boss + 15] == 2:
            break
    assert pb.memory[PL + 2] == 8, (
        f"Serpent AOE did not deal its fixed two damage: hp={pb.memory[PL + 2]}")
    pb.memory[boss + 10] = 1
    before_growth = pb.memory[boss + 21]
    for _ in range(4):
        pb.tick()
        if pb.memory[boss + 21] != before_growth:
            break
    assert pb.memory[boss + 21] == before_growth - 1, (
        "Serpent did not visibly contract after its blast")

    # Verdant now shares the true 224px Colossus field. Walk its eastern half
    # rather than testing the obsolete decorative 0..3px compact-room sway.
    put16(pb, PL + 9, 200)
    scx = []
    for _ in range(80):
        pb.tick()
        scx.append(pb.memory[0xFF43])
    assert pb.memory[CAMERA_X] == 64 and 61 <= scx[-1] <= 67, (
        f"Serpent field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scx[-1]}")

    screenshot = ROOT / "tmp" / "serpent-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    assert rune_art(0x0F) != rune_art(0x2F), (
        "Serpent lightning stopped travelling through the coil")
    print(f"[colossal-serpent] PASS growth {counts}, mote feeding, "
          f"{hostile}-lane bullet hell + 2-damage AOE, contraction, "
          "camera 0..64, animated charge")


if __name__ == "__main__":
    main()
