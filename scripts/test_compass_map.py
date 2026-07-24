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
BGT_MAP_NODE_ROOM_BASE = 102
BGT_MAP_NODE_UNKNOWN_BASE = 106
BGT_MAP_NODE_HERE_BASE = 110
BGT_MAP_NODE_BOSS_BASE = 114
BGT_MAP_NODE_SIGIL_BASE = 118
BGT_MAP_NODE_TRIAL_BASE = 122

GX = (1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16)
GY = (1, 1, 1, 1, 1, 1,
      4, 4, 4, 4, 4, 4,
      7, 7, 7, 7, 7, 7,
      10, 10, 10, 10, 10, 10,
      13, 13, 13, 13, 13, 13)


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


def node_tiles(pb: PyBoy, cell: int) -> tuple[int, int, int, int]:
    x, y = GX[cell], GY[cell]
    return (map_tile(pb, x, y), map_tile(pb, x + 1, y),
            map_tile(pb, x, y + 1), map_tile(pb, x + 1, y + 1))


def expected_node(base: int) -> tuple[int, int, int, int]:
    return base, base + 1, base + 2, base + 3


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

    # Every room is a true 16x16 square in the fixed 6x5 abstract lattice.
    # The opening map shows the current room and just its immediate hollow
    # frontier. Deeper cells/links remain blank until exploration reaches
    # them, so SELECT reads as travel history rather than a solved circuit.
    assert node_tiles(pb, 0) == expected_node(BGT_MAP_NODE_HERE_BASE), \
        "Compass lost its 16x16 current-room node"
    assert node_tiles(pb, 1) == expected_node(BGT_MAP_NODE_UNKNOWN_BASE), \
        "Compass lost its immediate 16x16 frontier room"
    assert map_tile(pb, 3, 2) == BGT_MAP_PATH_H_DIM, \
        "Compass lost the dim frontier connection"
    assert map_tile(pb, GX[2], GY[2]) == BGT_VOID, \
        "Compass revealed a room beyond the immediate frontier"
    assert map_tile(pb, 17, 3) == BGT_VOID, \
        "Compass revealed a disconnected deeper vertical route"
    assert map_tile(pb, 0, 0) == BGT_VOID, "Compass retained text-page background"
    assert (map_tile(pb, 8, 0), map_tile(pb, 9, 0), map_tile(pb, 10, 0)) == (
        BGT_AREA_M, BGT_AREA_A, BGT_MAP_LABEL_P), \
        "Compass lost its tile-native MAP heading"
    assert map_tile(pb, 1, 16) == BGT_MAP_HERE, "Compass lost YOU legend icon"
    assert map_tile(pb, 2, 16) == BGT_MAP_LABEL_Y, "Compass lost YOU legend"
    assert map_tile(pb, 15, 16) == BGT_MAP_BOSS, "Compass lost BOSS legend icon"
    assert map_tile(pb, 16, 16) == BGT_MAP_LABEL_B, "Compass lost BOSS legend"
    assert sum(map_tile(pb, GX[i], GY[i]) == BGT_MAP_NODE_UNKNOWN_BASE
               for i in range(20)) == 1, \
        "Compass opening frontier is not a single readable next room"
    assert map_tile(pb, GX[20], GY[20]) == BGT_VOID, \
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
    pb.memory[rs + 29] = 0xFF
    pb.memory[rs + 31] = 0x07
    pb.memory[rs + 33] = 0
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert node_tiles(pb, 18) == expected_node(BGT_MAP_NODE_HERE_BASE), \
        (f"sanctuary current marker is misplaced: room={pb.memory[rs + 1]} "
         f"bosses={pb.memory[rs + 11]} tile={map_tile(pb, GX[18], GY[18])} "
         f"here={[(x, y) for y in range(15) for x in range(20) if map_tile(pb, x, y) == BGT_MAP_NODE_HERE_BASE]}")
    assert node_tiles(pb, 19) == expected_node(BGT_MAP_NODE_BOSS_BASE), \
        "Compass did not hint the boss node"
    assert map_tile(pb, 15, 11) == BGT_MAP_PATH_H, \
        "Compass did not connect sanctuary to the hinted boss"
    assert node_tiles(pb, 2) == expected_node(BGT_MAP_NODE_SIGIL_BASE), \
        "Compass did not place the Rift Sigil in its owning room"
    assert node_tiles(pb, 0) == expected_node(BGT_MAP_NODE_ROOM_BASE), \
        "visited room lost its square glyph"
    assert map_tile(pb, 17, 9) == BGT_MAP_PATH_V, \
        "Compass vertical turn is not obvious"
    assert map_tile(pb, 0, 1) == BGT_VOID and map_tile(pb, 18, 10) == BGT_VOID, \
        "dungeon graph escaped its active lattice"

    # Semantic nodes must be distinguishable in the rendered CGB image, not
    # merely assigned nominally different attribute bytes that all load the
    # same palette. Each glyph's center is a color-3 pixel.
    image = pb.screen.image
    here_rgb = image.getpixel((GX[18] * 8 + 8, GY[18] * 8 + 8))[:3]
    boss_rgb = image.getpixel((GX[19] * 8 + 8, GY[19] * 8 + 8))[:3]
    sigil_rgb = image.getpixel((GX[2] * 8 + 8, GY[2] * 8 + 8))[:3]
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
    assert map_tile(pb, 9, 3) == BGT_MAP_RIFT, \
        "Compass did not reveal the discovered rift endpoint"
    assert map_tile(pb, 9, 4) == BGT_VOID, \
        "Compass revealed an undiscovered rift destination"
    assert map_tile(pb, 7, 17) == BGT_MAP_RIFT, "Compass lost RIFT legend icon"
    assert (map_tile(pb, 8, 17), map_tile(pb, 9, 17),
            map_tile(pb, 10, 17), map_tile(pb, 11, 17)) == (
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
               for x, y in ((9, 3), (9, 4))), \
        "Compass did not connect both discovered rift endpoints"
    # The diamond is intentionally hollow at its exact centre; sample one of
    # its authored lit pixels rather than mistaking that hole for palette loss.
    rift_rgb = pb.screen.image.getpixel((9 * 8 + 2, 3 * 8 + 3))[:3]
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
    assert node_tiles(pb, 7) == expected_node(BGT_MAP_NODE_TRIAL_BASE), \
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
    assert node_tiles(pb, 9) == expected_node(BGT_MAP_NODE_TRIAL_BASE), \
        "completed Waystone did not reveal the deep Warden"

    # The final dungeon must exercise all four explored-room bytes. A fully
    # explored sanctuary shows all thirty cells, the extra-byte current
    # marker, and the adjacent Void boss hint.
    pb.button("b")
    for _ in range(30):
        pb.tick()
    pb.memory[rs + 11] = 8
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[8] - 1
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 29] = 0xFF
    pb.memory[rs + 31] = 0xFF
    pb.memory[rs + 33] = 0x1F
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert node_tiles(pb, 28) == expected_node(BGT_MAP_NODE_HERE_BASE), \
        "extra-byte sanctuary marker is misplaced"
    assert node_tiles(pb, 29) == expected_node(BGT_MAP_NODE_BOSS_BASE), \
        "thirty-room Compass lost the final boss hint"
    assert all(map_tile(pb, GX[i], GY[i]) != BGT_MAP_NODE_UNKNOWN_BASE
               for i in range(30)), \
        "thirty-room Compass failed to render explored extra-byte cells"
    pb.screen.image.save(ROOT / "tmp" / "compass-thirty-room.png")
    pb.stop(save=False)
    print(f"[compass-map] PASS 20→30 room 6x5 maze with 16x16 nodes "
          f"+ staged route cues "
          f"+ semantic colors "
          f"here={here_rgb} sigil/rift={sigil_rgb} boss={boss_rgb} "
          "+ nonlinear link + high-byte exploration")


if __name__ == "__main__":
    main()
