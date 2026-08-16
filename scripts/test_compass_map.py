#!/usr/bin/env python3
"""Live-ROM contract: SELECT renders the explored dungeon as a tile grid."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_cache_cell,
    dungeon_maze_neighbor, dungeon_size, mission_graph,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_VOID = 0
BGT_FLOOR = 1
BGT_WALL = 2
HUD_DIGIT_0 = 9
BGT_MAP_ROOM = 49
BGT_MAP_HERE = 50
BGT_MAP_BOSS = 51
BGT_MAP_SIGIL = 52
BGT_MAP_PATH_H = 53
BGT_MAP_PATH_V = 54
BGT_MAP_LABEL_Y = 64
BGT_MAP_LABEL_S = 67
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
BGT_MAP_BIG_ROOM = 102
BGT_MAP_BIG_UNKNOWN = 106
BGT_MAP_BIG_HERE = 110
BGT_MAP_BIG_GOAL = 114
BGT_MAP_BIG_BOSS = 118
BGT_MAP_CACHE = 122
BGT_MAP_BIG_CACHE = 123
SPR_CLASS_ASCENDED_BASE = 102
ASCENDED_TILE_COUNT = 20
GX = (1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16)
GY = (2, 2, 2, 2, 2, 2,
      5, 5, 5, 5, 5, 5,
      8, 8, 8, 8, 8, 8,
      11, 11, 11, 11, 11, 11,
      14, 14, 14, 14, 14, 14)


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


def node_tile(pb: PyBoy, cell: int) -> int:
    return map_tile(pb, GX[cell], GY[cell])


def open_compass(pb: PyBoy, screen: int) -> None:
    """Hold SELECT until the cartridge completes the real screen handoff."""
    pb.button_press("select")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == SCREEN_MAP:
                # loop_current_screen flips before the banked map_enter has
                # finished loading its tile atlas, attributes, and full 6x5
                # grid. Let that transaction finish before sampling VRAM.
                for _ in range(90):
                    pb.tick()
                return
    finally:
        pb.button_release("select")
    raise AssertionError("SELECT did not enter Spirit Compass")


def close_compass(pb: PyBoy, screen: int, player: int) -> None:
    """Return through room_enter and let its banked resume work finish."""
    pb.button_press("b")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == SCREEN_ROOM:
                break
        else:
            raise AssertionError("B did not return from Spirit Compass")
    finally:
        pb.button_release("b")
    # loop_current_screen changes before room_enter's sprite/palette restore
    # has necessarily returned. Keep this map-rendering fixture safe while
    # that real transaction settles instead of guessing it still takes the
    # historical fixed 30 frontend frames.
    for _ in range(90):
        pb.memory[player + 2] = 14
        pb.memory[player + 15] = 60
        pb.tick()


def main() -> None:
    screen = addr("_loop_current_screen")
    rs = addr("_run_state")
    player = addr("_player")
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
    seed = sum(pb.memory[rs + 2 + i] << (i * 8) for i in range(4))
    graph0 = mission_graph(dungeon_size(0), seed, 0)
    ascended_before = bytes(pb.memory[
        0x8000 + SPR_CLASS_ASCENDED_BASE * 16:
        0x8000 + (SPR_CLASS_ASCENDED_BASE + ASCENDED_TILE_COUNT) * 16])

    open_compass(pb, screen)
    assert pb.memory[screen] == SCREEN_MAP, "SELECT did not enter Spirit Compass"

    # The complete active 6x5 footprint is a screen-filling grid of 2x2
    # metasquares. Unknown rooms/corridors stay dim while walked rooms/links
    # brighten, making both scale and fill-in behavior obvious immediately.
    assert node_tile(pb, 0) == BGT_MAP_BIG_HERE, \
        "Compass lost its full-size current-room node"
    assert node_tile(pb, graph0["trial"]) == BGT_MAP_BIG_GOAL, \
        "Compass did not expose the generated opening Trial"
    assert node_tile(pb, graph0["sigil"]) == BGT_MAP_BIG_UNKNOWN, \
        "Compass exposed a later Sigil before the Trial"
    assert map_tile(pb, 3, 2) == BGT_MAP_PATH_H, \
        "Compass did not brighten the first step toward the active objective"
    assert map_tile(pb, 3, 3) == BGT_MAP_PATH_H, \
        "Compass route cue does not span the full node height"
    assert node_tile(pb, 19) == BGT_MAP_BIG_UNKNOWN, \
        "Compass did not expose the opening dungeon's full abstract footprint"
    assert map_tile(pb, 0, 0) == BGT_VOID, "Compass retained text-page background"
    assert (map_tile(pb, 6, 0), map_tile(pb, 7, 0),
            map_tile(pb, 9, 0), map_tile(pb, 10, 0),
            map_tile(pb, 11, 0)) == (
                BGT_MAP_LABEL_S, HUD_DIGIT_0 + 1,
                BGT_AREA_M, BGT_AREA_A, BGT_MAP_LABEL_P), \
        "Compass lost its tile-native S1 MAP heading"
    assert map_tile(pb, 0, 17) == BGT_MAP_HERE, "Compass lost YOU key icon"
    assert map_tile(pb, 1, 17) == BGT_MAP_LABEL_Y, "Compass lost YOU key"
    assert map_tile(pb, 4, 17) == BGT_MAP_SIGIL, "Compass lost GOAL key icon"
    assert map_tile(pb, 9, 17) == BGT_MAP_BOSS, "Compass lost BOSS key icon"
    assert map_tile(pb, 10, 17) == BGT_MAP_LABEL_B, "Compass lost BOSS key"
    assert map_tile(pb, 14, 17) == BGT_MAP_CACHE, "Compass lost LOOT key icon"
    cache = dungeon_cache_cell(dungeon_size(0), seed, 0)
    assert node_tile(pb, cache) == BGT_MAP_BIG_CACHE, \
        f"Compass did not reveal optional cache cell {cache}"
    assert sum(node_tile(pb, i) == BGT_MAP_BIG_UNKNOWN for i in range(20)) == 17, \
        "Compass opening footprint is not a full dim 20-room grid"
    assert tuple(map_tile(pb, 19, y) for y in (2, 5, 8, 11)) == (
        HUD_DIGIT_0 + 1, HUD_DIGIT_0 + 2,
        HUD_DIGIT_0 + 3, HUD_DIGIT_0 + 4), \
        "Compass lost its numbered dungeon depth bands"
    assert node_tile(pb, 20) == BGT_VOID, \
        "opening Compass leaked an inactive late-stage node"
    # HERE is a pin, not the former directional arrow, and owns palette 7
    # rather than borrowing the cyan door/cache language. Pin both its small
    # legend geometry and the live current-node attribute in cartridge VRAM.
    expected_pin = bytes((
        0x3C, 0x3C, 0x7E, 0x7E, 0xC3, 0xFF, 0xC3, 0xFF,
        0x7E, 0x7E, 0x3C, 0x3C, 0x18, 0x18, 0x18, 0x18,
    ))
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    tile_base = 0x8000 if lcdc & 0x10 else 0x9000
    assert bytes(pb.memory[tile_base + BGT_MAP_HERE * 16:
                           tile_base + (BGT_MAP_HERE + 1) * 16]) == expected_pin, \
        "Compass current marker reverted from the unambiguous map pin"
    pb.memory[0xFF4F] = 1
    assert pb.memory[0x9800 + GY[0] * 32 + GX[0]] == 7, \
        "Compass current node lost its dedicated player palette"
    assert pb.memory[0x9800 + 17 * 32] == 7, \
        "Compass YOU key does not match the current-node palette"
    pb.memory[0xFF4F] = 0
    pb.memory[0xFF40] = lcdc
    pb.screen.image.save(ROOT / "tmp" / "compass-first-room.png")

    close_compass(pb, screen, player)
    assert pb.memory[screen] == SCREEN_ROOM, "B did not return from Spirit Compass"
    ascended_after = bytes(pb.memory[
        0x8000 + SPR_CLASS_ASCENDED_BASE * 16:
        0x8000 + (SPR_CLASS_ASCENDED_BASE + ASCENDED_TILE_COUNT) * 16])
    assert ascended_after == ascended_before, \
        "SELECT return did not restore the five transformation sprite atlases"

    # Room one is the dungeon's first true junction. The Sigil wing continues
    # east while the deeper route branches south to room ten. Both real doors
    # must appear as equally clear hollow frontier squares, proving that this
    # is an abstract spatial map rather than a decorated linear room counter.
    pb.memory[rs + 1] = STAGE_START[0] + 1
    pb.memory[rs + 20] = 0x03
    pb.memory[rs + 29] = 0
    pb.memory[rs + 31] = 0
    pb.memory[rs + 33] = 0
    pb.memory[rs + 27] |= 1 << 0  # opening Trial completed
    if graph0["order"]:
        pb.memory[rs + 27] |= 1 << 3  # seed orders Warden before Sigil
    open_compass(pb, screen)
    assert node_tile(pb, 1) == BGT_MAP_BIG_HERE, \
        "Compass lost current marker at objective-wing junction"
    assert node_tile(pb, graph0["sigil"]) == BGT_MAP_BIG_GOAL, \
        "Compass lost the generated Sigil objective"
    assert node_tile(pb, 10) == BGT_MAP_BIG_UNKNOWN, \
        "Compass lost southward deep-route frontier"
    # Resolve the cartridge's first BFS step so this remains valid across all
    # eight seed-selected folds rather than assuming the old eastward room 2.
    parents, queue = {1: None}, [1]
    for cell in queue:
        if cell == graph0["sigil"]:
            break
        for direction in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, dungeon_size(0), direction, seed, 0)
            if neighbor is not None and neighbor not in parents:
                parents[neighbor] = cell
                queue.append(neighbor)
    step = graph0["sigil"]
    while parents[step] != 1:
        step = parents[step]
    if GX[step] == GX[1]:
        link_x, link_y, link_tile = GX[1], min(GY[1], GY[step]) + 2, BGT_MAP_PATH_V
    else:
        link_x, link_y, link_tile = min(GX[1], GX[step]) + 2, GY[1], BGT_MAP_PATH_H
    assert map_tile(pb, link_x, link_y) == link_tile, (
        f"Compass did not highlight generated Sigil route via {step}: "
        f"{map_tile(pb, link_x, link_y)}")
    # Fill-in must read by shape as well as palette. Cell zero is explored:
    # its interior carries a visible dotted fill. Cell two is unvisited:
    # its centre stays dark and its top edge alternates lit/gap pixels as a
    # dashed square. This remains legible on low-contrast LCDs and grayscale
    # captures where two shades of green alone are not an adequate contract.
    junction_image = pb.screen.image
    visited_fill_rgb = junction_image.getpixel((
        GX[0] * 8 + 2, GY[0] * 8 + 1))[:3]
    unknown_fill_rgb = junction_image.getpixel((
        GX[10] * 8 + 2, GY[10] * 8 + 1))[:3]
    unknown_edge_rgb = junction_image.getpixel((
        GX[10] * 8, GY[10] * 8))[:3]
    unknown_gap_rgb = junction_image.getpixel((
        GX[10] * 8 + 1, GY[10] * 8))[:3]
    assert visited_fill_rgb != unknown_fill_rgb, (
        f"explored room lost its filled interior: "
        f"{visited_fill_rgb} == {unknown_fill_rgb}")
    assert unknown_edge_rgb != unknown_gap_rgb, (
        f"unvisited room lost its dashed square: "
        f"{unknown_edge_rgb} == {unknown_gap_rgb}")
    pb.screen.image.save(ROOT / "tmp" / "compass-objective-junction.png")
    close_compass(pb, screen, player)
    assert pb.memory[screen] == SCREEN_ROOM, \
        "B did not return from objective-wing Compass"

    # Visiting the sanctuary cell reveals the adjacent danger node and the
    # connecting line before the player commits to the boss room.
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[0] - 1
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 29] = 0xFF
    pb.memory[rs + 31] = 0x07
    pb.memory[rs + 33] = 0
    open_compass(pb, screen)
    assert node_tile(pb, 18) == BGT_MAP_BIG_HERE, \
        (f"sanctuary current marker is misplaced: room={pb.memory[rs + 1]} "
         f"bosses={pb.memory[rs + 11]} tile={map_tile(pb, GX[18], GY[18])} "
         f"here={[(x, y) for y in range(17) for x in range(20) if map_tile(pb, x, y) == BGT_MAP_BIG_HERE]}")
    assert node_tile(pb, 19) == BGT_MAP_BIG_BOSS, \
        "Compass did not hint the boss node"
    assert map_tile(pb, 15, 11) == BGT_MAP_PATH_H, \
        "Compass did not connect sanctuary to the hinted boss"
    assert node_tile(pb, graph0["sigil"]) == BGT_MAP_BIG_GOAL, \
        "Compass did not place the Rift Sigil in its owning room"
    assert node_tile(pb, 0) == BGT_MAP_BIG_ROOM, \
        "visited room lost its square glyph"
    vertical_links = []
    for source in range(dungeon_size(0)):
        target = dungeon_maze_neighbor(
            source, dungeon_size(0), 2, seed, 0)
        if target is not None:
            vertical_links.append((
                GX[source], min(GY[source], GY[target]) + 2))
    assert len(vertical_links) >= 3, vertical_links
    assert all(map_tile(pb, x, y) == BGT_MAP_PATH_V
               for x, y in vertical_links), \
        f"Compass did not render generated vertical folds: {vertical_links}"
    assert map_tile(pb, 0, 2) == BGT_VOID and map_tile(pb, 18, 11) == BGT_VOID, \
        "dungeon graph escaped its active lattice"

    # Semantic nodes must be distinguishable in the rendered CGB image, not
    # merely assigned nominally different attribute bytes that all load the
    # same palette. Each glyph's center is a color-3 pixel.
    image = pb.screen.image
    # Sample authored interior strokes rather than the common outline.
    here_rgb = image.getpixel((GX[18] * 8 + 6, GY[18] * 8 + 6))[:3]
    boss_rgb = image.getpixel((GX[19] * 8 + 3, GY[19] * 8 + 5))[:3]
    # The objective is a large centered exclamation mark. Sample its stem,
    # not the empty left interior retained inside the common node outline.
    sigil_rgb = image.getpixel((
        GX[graph0["sigil"]] * 8 + 6,
        GY[graph0["sigil"]] * 8 + 5))[:3]
    assert len({here_rgb, boss_rgb, sigil_rgb}) == 3, (
        f"Compass semantic colors collapsed: here={here_rgb} "
        f"boss={boss_rgb} sigil={sigil_rgb}")
    shot = ROOT / "tmp" / "compass-semantic-colors.png"
    image.save(shot)

    # Once collected, the Rift Sigil room returns to an ordinary explored
    # node. A stale GOAL marker used to keep sending players back to a
    # completed fixture.
    close_compass(pb, screen, player)
    pb.memory[rs + 23] |= 1
    open_compass(pb, screen)
    assert node_tile(pb, graph0["sigil"]) == BGT_MAP_BIG_ROOM, \
        "completed Rift Sigil remained marked as an active GOAL"

    # Later dungeons own a reversible nonlinear link between local rooms 2
    # and 8. Seeing the first endpoint reveals only its violet end-cap; after
    # both rooms are known, a diagonal chain describes the real teleport edge
    # without mislabeling it as a cardinal corridor.
    close_compass(pb, screen, player)
    pb.memory[rs + 11] = 1
    pb.memory[rs + 37] = 0
    pb.memory[rs + 1] = STAGE_START[1] + 2
    pb.memory[rs + 20] = 0x07    # cells 0, 1, and 2 seen
    pb.memory[rs + 29] = 0
    open_compass(pb, screen)
    assert map_tile(pb, 9, 4) == BGT_MAP_RIFT, \
        (f"Compass did not reveal the discovered rift endpoint: "
         f"tile={map_tile(pb, 9, 4)} screen={pb.memory[screen]} "
         f"room={pb.memory[rs + 1]} bosses={pb.memory[rs + 11]} "
         f"world={pb.memory[rs + 17]} seen={pb.memory[rs + 20]:02x}")

    close_compass(pb, screen, player)
    pb.memory[rs + 1] = STAGE_START[1] + 8
    pb.memory[rs + 20] = 0x07    # cells 0, 1, and 2 seen
    pb.memory[rs + 29] = 0x01    # cell 8 seen
    open_compass(pb, screen)
    assert map_tile(pb, 9, 4) == BGT_MAP_RIFT, \
        "Compass did not preserve the discovered rift shortcut"
    # The diamond is intentionally hollow at its exact centre; sample one of
    # its authored lit pixels rather than mistaking that hole for palette loss.
    rift_rgb = pb.screen.image.getpixel((9 * 8 + 2, 4 * 8 + 3))[:3]
    assert rift_rgb == sigil_rgb, (
        f"rift edge lost its violet semantic color: {rift_rgb} != {sigil_rgb}")
    pb.screen.image.save(ROOT / "tmp" / "compass-rift-link.png")

    # Back-half fixtures are revealed one at a time instead of allowing the
    # player to cut diagonally from the first Warden to the sanctuary.
    close_compass(pb, screen, player)
    pb.memory[rs + 11] = 2
    pb.memory[rs + 37] = 0
    pb.memory[rs + 1] = STAGE_START[2] + 4
    pb.memory[rs + 20] = 0x1F
    pb.memory[rs + 23] |= 1 << 2
    pb.memory[rs + 27] = (1 << 0) | (1 << 3)
    pb.memory[rs + 28] = 0
    open_compass(pb, screen)
    graph2 = mission_graph(dungeon_size(2), seed, 2)
    assert node_tile(pb, graph2["waystone"]) == BGT_MAP_BIG_GOAL, \
        "completed first Warden did not reveal the Waystone puzzle"

    close_compass(pb, screen, player)
    pb.memory[rs + 11] = 5
    pb.memory[rs + 37] = 0
    pb.memory[rs + 1] = STAGE_START[5] + 7
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 23] |= 1 << 5
    pb.memory[rs + 27] = (1 << 0) | (1 << 3) | (1 << 7)
    pb.memory[rs + 28] = 0
    open_compass(pb, screen)
    graph5 = mission_graph(dungeon_size(5), seed, 5)
    assert node_tile(pb, graph5["deep_warden"]) == BGT_MAP_BIG_GOAL, \
        "completed Waystone did not reveal the deep Warden"

    # The final dungeon must exercise all four explored-room bytes. A fully
    # explored sanctuary shows all thirty cells, the extra-byte current
    # marker, and the adjacent Void boss hint.
    close_compass(pb, screen, player)
    pb.memory[rs + 11] = 8
    pb.memory[rs + 37] = 0
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[8] - 1
    pb.memory[rs + 20] = 0xFF
    pb.memory[rs + 29] = 0xFF
    pb.memory[rs + 31] = 0xFF
    pb.memory[rs + 33] = 0x1F
    open_compass(pb, screen)
    assert node_tile(pb, 28) == BGT_MAP_BIG_HERE, \
        "extra-byte sanctuary marker is misplaced"
    assert node_tile(pb, 29) == BGT_MAP_BIG_BOSS, \
        "thirty-room Compass lost the final boss hint"
    assert map_tile(pb, 7, 0) == HUD_DIGIT_0 + 9, \
        "final Compass heading did not identify stage nine"
    assert all(node_tile(pb, i) != BGT_MAP_BIG_UNKNOWN for i in range(30)), \
        "thirty-room Compass failed to render explored extra-byte cells"
    pb.screen.image.save(ROOT / "tmp" / "compass-thirty-room.png")

    # Riftwild's legend shares VRAM slots 90..92 with in-play district
    # lettering. The Compass atlas must load last: the previous order left
    # the visible key reading PNIHT instead of RIFT.
    close_compass(pb, screen, player)
    pb.memory[rs + 17] = 1       # world_mode
    pb.memory[rs + 18] = 0       # world_screen
    pb.memory[rs + 21] = 0xFF    # world_seen low
    pb.memory[rs + 22] = 0xFF    # world_seen high
    open_compass(pb, screen)
    assert tuple(map_tile(pb, x, 10) for x in range(14, 18)) == (
        BGT_MAP_LABEL_R, BGT_MAP_LABEL_I,
        BGT_MAP_LABEL_F, BGT_MAP_LABEL_T), \
        "Riftwild Compass lost its RIFT legend tile ids"
    world_image = pb.screen.image
    letter_rgb = world_image.getpixel((15 * 8 + 3, 10 * 8))[:3]
    r_diagonal_rgb = world_image.getpixel((14 * 8 + 4, 10 * 8 + 4))[:3]
    f_bar_rgb = world_image.getpixel((16 * 8 + 3, 10 * 8))[:3]
    # The old shared-slot corruption rendered PNIHT. R's lower diagonal is
    # absent from P, while F's broad top bar is absent from H.
    assert r_diagonal_rgb == letter_rgb, \
        f"RIFT R still renders as P: {r_diagonal_rgb} != {letter_rgb}"
    assert f_bar_rgb == letter_rgb, \
        f"RIFT F still renders as H: {f_bar_rgb} != {letter_rgb}"
    world_image.save(ROOT / "tmp" / "compass-riftwild-legend.png")
    pb.stop(save=False)
    print(f"[compass-map] PASS 20→30 room 6x5 screen-filling pocket grid "
          f"+ dotted explored rooms + dashed unknown squares "
          f"+ bright explored route + staged cues "
          f"+ semantic colors "
          f"here={here_rgb} sigil/rift={sigil_rgb} boss={boss_rgb} "
          "+ nonlinear link + high-byte exploration + RIFT legend + sprite restore")


if __name__ == "__main__":
    main()
