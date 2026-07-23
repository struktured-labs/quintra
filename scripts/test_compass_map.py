#!/usr/bin/env python3
"""Live-ROM contract: SELECT renders the explored dungeon as a tile grid."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM, STAGE_START

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_VOID = 0
BGT_FLOOR = 1
BGT_WALL = 2
BGT_MAP_ROOM = 49
BGT_MAP_HERE = 50
BGT_MAP_BOSS = 51
BGT_MAP_SIGIL = 52
BGT_MAP_PATH_H = 53
BGT_MAP_PATH_V = 54
BGT_MAP_LABEL_Y = 64
BGT_MAP_LABEL_I = 68
BGT_MAP_LABEL_B = 71
BGT_MAP_RIFT = 90
BGT_MAP_LABEL_R = 91
BGT_MAP_LABEL_F = 92
BGT_MAP_LABEL_T = 93
BGT_AREA_M = 87
BGT_AREA_A = 84
BGT_MAP_LABEL_P = 94
BGT_MAP_UNKNOWN = 95
BGT_MAP_PATH_H_DIM = 100
BGT_MAP_PATH_V_DIM = 101
BGT_SWITCH = 33

GX = (1, 5, 9, 13, 17, 17, 13, 9, 5, 1,
      1, 5, 9, 13, 17, 17, 13, 9, 5, 1)
GY = (3, 3, 3, 3, 3, 6, 6, 6, 6, 6,
      9, 9, 9, 9, 9, 12, 12, 12, 12, 12)


def addr(name: str) -> int:
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def map_tile(pb: PyBoy, x: int, y: int) -> int:
    # `set_bkg_tiles` writes the 0x9800 map. The Compass owns this map while
    # SELECT is open, so inspecting it proves a real tile-built grid rather
    # than a text-only status page or a host screenshot interpretation.
    return pb.memory[0x9800 + y * 32 + x]


def main() -> None:
    screen = addr("_loop_current_screen")
    rs = addr("_run_state")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(90):
        pb.tick()
    assert pb.memory[screen] == SCREEN_ROOM, "could not reach a live dungeon room"

    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert pb.memory[screen] == SCREEN_MAP, "SELECT did not enter Spirit Compass"

    # The first room is one bright glyph in the fixed 5x4 abstract lattice.
    # This fourteen-room opening stage exposes thirteen dim destinations and its
    # compressed lattice without leaking room identities. Traversed links
    # replace these subdued planning lines with the bright path glyphs.
    assert map_tile(pb, GX[0], GY[0]) == BGT_MAP_HERE, \
        "Compass lost current-room glyph"
    assert map_tile(pb, GX[1], GY[1]) == BGT_MAP_UNKNOWN, \
        "Compass lost its dim unexplored-room slot"
    assert all(map_tile(pb, x, 3) == BGT_MAP_PATH_H_DIM
               for x in (2, 3, 4)), \
        "Compass lost the dim unexplored horizontal lattice"
    assert all(map_tile(pb, 1, y) == BGT_MAP_PATH_V_DIM
               for y in (4, 5)), \
        "Compass lost the dim unexplored vertical lattice"
    assert map_tile(pb, 0, 0) == BGT_VOID, "Compass retained text-page background"
    assert (map_tile(pb, 8, 1), map_tile(pb, 9, 1), map_tile(pb, 10, 1)) == (
        BGT_AREA_M, BGT_AREA_A, BGT_MAP_LABEL_P), \
        "Compass lost its tile-native MAP heading"
    assert map_tile(pb, 1, 15) == BGT_MAP_HERE, "Compass lost YOU legend icon"
    assert map_tile(pb, 2, 15) == BGT_MAP_LABEL_Y, "Compass lost YOU legend"
    assert map_tile(pb, 15, 15) == BGT_MAP_BOSS, "Compass lost BOSS legend icon"
    assert map_tile(pb, 16, 15) == BGT_MAP_LABEL_B, "Compass lost BOSS legend"
    assert sum(map_tile(pb, GX[i], GY[i]) == BGT_MAP_UNKNOWN
               for i in range(14)) == 13, \
        "Compass did not expose the fourteen-slot opening lattice"
    assert map_tile(pb, GX[14], GY[14]) == BGT_VOID, \
        "opening Compass leaked an inactive late-stage node"
    pb.screen.image.save(ROOT / "tmp" / "compass-first-room.png")

    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[screen] == SCREEN_ROOM, "B did not return from Spirit Compass"

    # Visiting the sanctuary cell reveals the adjacent danger node and the
    # connecting line before the player commits to the boss room.
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[0] - 1
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 29] = 0x1F
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert map_tile(pb, GX[12], GY[12]) == BGT_MAP_HERE, \
        (f"sanctuary current marker is misplaced: room={pb.memory[rs + 1]} "
         f"bosses={pb.memory[rs + 11]} tile={map_tile(pb, GX[12], GY[12])} "
         f"here={[(x, y) for y in range(15) for x in range(20) if map_tile(pb, x, y) == BGT_MAP_HERE]}")
    assert map_tile(pb, GX[13], GY[13]) == BGT_MAP_BOSS, \
        "Compass did not hint the boss node"
    assert all(map_tile(pb, x, 9) == BGT_MAP_PATH_H for x in (10, 11, 12)), \
        "Compass did not connect sanctuary to the hinted boss"
    assert map_tile(pb, GX[2], GY[2]) == BGT_MAP_SIGIL, \
        "Compass did not place the Rift Sigil in its owning room"
    assert map_tile(pb, GX[0], GY[0]) == BGT_MAP_ROOM, \
        "visited room lost its square glyph"
    assert all(map_tile(pb, 17, y) == BGT_MAP_PATH_V for y in (4, 5)), \
        "Compass vertical turn is not obvious"
    assert map_tile(pb, 0, 3) == BGT_VOID and map_tile(pb, 18, 9) == BGT_VOID, \
        "dungeon graph escaped its active lattice"

    # Semantic nodes must be distinguishable in the rendered CGB image, not
    # merely assigned nominally different attribute bytes that all load the
    # same palette. Each glyph's center is a color-3 pixel.
    image = pb.screen.image
    here_rgb = image.getpixel((GX[12] * 8 + 4, GY[12] * 8 + 4))[:3]
    boss_rgb = image.getpixel((GX[13] * 8 + 4, GY[13] * 8 + 4))[:3]
    sigil_rgb = image.getpixel((GX[2] * 8 + 4, GY[2] * 8 + 4))[:3]
    assert len({here_rgb, boss_rgb, sigil_rgb}) == 3, (
        f"Compass semantic colors collapsed: here={here_rgb} "
        f"boss={boss_rgb} sigil={sigil_rgb}")
    shot = ROOT / "tmp" / "compass-semantic-colors.png"
    image.save(shot)

    # Later dungeons own a reversible nonlinear link between local rooms 2
    # and 8. Seeing the first endpoint reveals only its violet end-cap; after
    # both rooms are known, a diagonal chain describes the real teleport edge
    # without mislabeling it as a cardinal corridor.
    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 11] = 1
    pb.memory[rs + 1] = STAGE_START[1] + 2
    pb.memory[rs + 20] = 0x07    # cells 0, 1, and 2 seen
    pb.memory[rs + 29] = 0
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert map_tile(pb, 8, 4) == BGT_MAP_RIFT, \
        "Compass did not reveal the discovered rift endpoint"
    assert all(map_tile(pb, x, y) == BGT_VOID
               for x, y in ((7, 4), (7, 5), (6, 5))), \
        "Compass revealed an undiscovered rift destination"
    assert map_tile(pb, 7, 13) == BGT_MAP_RIFT, "Compass lost RIFT legend icon"
    assert (map_tile(pb, 8, 13), map_tile(pb, 9, 13),
            map_tile(pb, 10, 13), map_tile(pb, 11, 13)) == (
                BGT_MAP_LABEL_R, BGT_MAP_LABEL_I,
                BGT_MAP_LABEL_F, BGT_MAP_LABEL_T), \
        "Compass lost RIFT legend"

    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 1] = STAGE_START[1] + 8
    pb.memory[rs + 20] = 0x07    # cells 0, 1, and 2 seen
    pb.memory[rs + 29] = 0x01    # cell 8 seen
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert all(map_tile(pb, x, y) == BGT_MAP_RIFT
               for x, y in ((8, 4), (7, 4), (7, 5), (6, 5))), \
        "Compass did not connect both discovered rift endpoints"
    # The diamond is intentionally hollow at its exact centre; sample one of
    # its authored lit pixels rather than mistaking that hole for palette loss.
    rift_rgb = pb.screen.image.getpixel((7 * 8 + 2, 4 * 8 + 3))[:3]
    assert rift_rgb == sigil_rgb, (
        f"rift edge lost its violet semantic color: {rift_rgb} != {sigil_rgb}")
    pb.screen.image.save(ROOT / "tmp" / "compass-rift-link.png")

    # Back-half fixtures are revealed one at a time instead of allowing the
    # player to cut diagonally from the first Warden to the sanctuary.
    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 11] = 2
    pb.memory[rs + 1] = STAGE_START[2] + 4
    pb.memory[rs + 20] = 0x1F
    pb.memory[rs + 23] |= 1 << 2
    pb.memory[rs + 27] = 1 << 3
    pb.memory[rs + 28] = 0
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert map_tile(pb, GX[7], GY[7]) == BGT_SWITCH, \
        "completed first Warden did not reveal the Waystone puzzle"

    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 11] = 5
    pb.memory[rs + 1] = STAGE_START[5] + 7
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 23] |= 1 << 5
    pb.memory[rs + 27] = (1 << 3) | (1 << 7)
    pb.memory[rs + 28] = 0
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert map_tile(pb, GX[9], GY[9]) == BGT_MAP_BOSS, \
        "completed Waystone did not reveal the deep Warden"

    # The final dungeon must exercise all three explored-room bytes. A fully
    # explored sanctuary shows all twenty cells, the extra-byte current
    # marker, and the adjacent Void boss hint.
    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 11] = 8
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[8] - 1
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 29] = 0xFF
    pb.memory[rs + 31] = 0x07
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert map_tile(pb, GX[18], GY[18]) == BGT_MAP_HERE, \
        "extra-byte sanctuary marker is misplaced"
    assert map_tile(pb, GX[19], GY[19]) == BGT_MAP_BOSS, \
        "twenty-room Compass lost the final boss hint"
    assert all(map_tile(pb, GX[i], GY[i]) != BGT_MAP_UNKNOWN
               for i in range(20)), \
        "twenty-room Compass failed to render explored extra-byte cells"
    pb.screen.image.save(ROOT / "tmp" / "compass-twenty-room.png")
    pb.stop(save=False)
    print(f"[compass-map] PASS 14→20 room 5x4 glyph grid + staged route cues "
          f"+ semantic colors "
          f"here={here_rgb} sigil/rift={sigil_rgb} boss={boss_rgb} "
          "+ nonlinear link + high-byte exploration")


if __name__ == "__main__":
    main()
