#!/usr/bin/env python3
"""Live-ROM contract for the secret merchants (Veil vaults + Riftwild caves).

Spec: docs/superpowers/specs/2026-11-16-secret-merchants.md.

* Every stage hides exactly one Veil Trader vault in a reachable,
  role-free dungeon cell (Python mirror of the cartridge's seeded pick,
  cross-checked against the ROM's own cache in that room).
* The host room's mouth is concealed (ordinary wall / ordinary cairn) and
  its tell is reachable from the room's trail crossing; no ware sits out in
  the open; the room's graph exits are intact (run stays solvable).
* A real BLAST reveal (player shot) opens the mouth, persists, and leads
  into the vault stall; tonic, bottle and charm purchases charge the right
  prices and apply; refusals and short purses charge nothing.
* Each Riftwild region hides three caves (one per band, never a den or
  landmark field) behind a closed STONE / BLAST / THICKET tell that opens
  only to its verb and leads to a cave merchant with a way home.

Set QUINTRA_MERCH_MEDIA=<dir> to save 4x screenshots and GIFs.
"""
import io
import os
from collections import deque
from pathlib import Path

from PIL import Image
from pyboy import PyBoy
from quintra_topology import (
    dungeon_cache_cell, dungeon_entry_cell, dungeon_maze_neighbor,
    dungeon_size, mission_graph,
)
from test_stage_archetypes import (
    EN, PL, RS, TM, addr, expected_graph_exits, generated_room, put16,
    reachable_exits,
)
import test_riftwild_dens as dens

MEDIA = os.environ.get("QUINTRA_MERCH_MEDIA")
ENTITY_SIZE = 28
ENT_PICKUP = 3
PICKUP_SHOP, WARE_SECRET = 4, 23
BGT_WALL, BGT_DOOR, BGT_BLOCK = 2, 3, 25
HOST_HERE = addr("_secret_merchant_host_here")
HOST_CACHE = addr("_secret_host_cell_cache")
CAVE_FIELDS = addr("_secret_cave_fields")
CAVE_KINDS = addr("_secret_cave_kinds")
KIND = addr("_room_hidden_secret_kind")
SX, SY = addr("_room_hidden_secret_x"), addr("_room_hidden_secret_y")
SX2, SY2 = addr("_room_hidden_secret_x2"), addr("_room_hidden_secret_y2")
# run_state tail appended by this feature (PRE_MERCHANT_RS_SIZE = 62).
RS_SHOP, RS_CHARMS, RS_CAVES = 62, 63, 65
SHOP_B, SHOP_C, SHOP_MOUTH, SHOP_ARMED, SHOP_FOUND = 0x01, 0x02, 0x04, 0x10, 0x80
PL_HPMAX, PL_HP, PL_FACING, PL_IFRAMES, PL_COINS = 1, 2, 13, 15, 16

STONE, BLAST, THICKET = 0, 1, 2
VEIL_KIND = (BLAST, THICKET, BLAST, STONE, STONE, BLAST, THICKET, BLAST, THICKET)
HIDDEN_FOR = {BLAST: 1, THICKET: 2, STONE: 3}   # SHOT / WALK / PUSH
TONIC_PRICE = (16, 18, 18, 16, 20, 20, 24, 18, 20)
CHARM_PRICE = (32, 45, 40, 45, 50, 50, 55, 60, 70)
GOLDEN = (0x00000000, 0x9E3779B9, 0x3C6EF372, 0xDAA66D2B, 0x78DDE6E4,
          0x1715609D, 0xB54CDA56, 0x5384540F, 0xF1BBCDC8)
RESERVED = {0, 2, 5, 8, 11, 15, 17, 23}
SEEDS = (0x5EC2E7, 0xCAFE1234, 0x0BADF00D)
CAVE_TX, CAVE_TY, CAVE_BASE = 16, 13, 48
EXCLUDED_FIELDS = {0, 1, 3, 5, 8, 16, 17, 21, 22, 23, 27, 29, 30, 32, 34, 35}
DEN_FIELDS_R0 = {dens.CAIRN_FIELD, dens.DROWNED_FIELD, dens.SCAR_FIELD}
WILD_STONE, WILD_MOUNTAIN, TREE, WILD_REEDS, PATH = 98, None, None, None, None


class Hash:
    def __init__(self, seed, stage, tag):
        self.s = (seed ^ GOLDEN[stage] ^ tag) & 0xFFFFFFFF or 0x2545F491

    def next(self):
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        self.s = s
        return (s >> 8) & 0xFF


def neighbors(cell, size, seed, stage):
    return [n for d in range(4)
            if (n := dungeon_maze_neighbor(cell, size, d, seed, stage)) is not None]


def mirror_host(seed, stage):
    size = dungeon_size(stage)
    entry = dungeon_entry_cell(size, seed, stage)
    cache = dungeon_cache_cell(size, seed, stage)
    roles = set(mission_graph(size, seed, stage)["sequence"])
    start = Hash(seed, stage, 0x5645494C).next() % size
    for dead_end_only in (True, False):
        for i in range(size):
            cell = (start + i) % size
            if (cell in (0, entry, cache) or cell + 3 >= size
                    or cell in RESERVED - {0} or cell in roles):
                continue
            if dead_end_only and len(neighbors(cell, size, seed, stage)) != 1:
                continue
            return cell
    return None


def graph_reachable(seed, stage, target):
    size = dungeon_size(stage)
    start = dungeon_entry_cell(size, seed, stage)
    seen, todo = {start}, deque([start])
    while todo:
        cell = todo.popleft()
        for n in neighbors(cell, size, seed, stage):
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return target in seen


def x4(image):
    return image.resize((image.width * 4, image.height * 4), Image.NEAREST)


def save(name, image):
    if MEDIA:
        Path(MEDIA).mkdir(parents=True, exist_ok=True)
        x4(image).save(Path(MEDIA) / name)


def save_gif(name, frames, ms=60):
    if MEDIA and frames:
        Path(MEDIA).mkdir(parents=True, exist_ok=True)
        big = [x4(f.convert("RGB")) for f in frames]
        big[0].save(Path(MEDIA) / name, save_all=True, append_images=big[1:],
                    duration=ms, loop=0)


def shop_wares(pb):
    out = []
    for i in range(32):
        e = EN + i * ENTITY_SIZE
        if (pb.memory[e] == ENT_PICKUP and pb.memory[e + 1] & 1
                and pb.memory[e + 17] == PICKUP_SHOP
                and pb.memory[e + 18] == WARE_SECRET):
            out.append(e)
    return out


def ware_at(pb, x):
    return next((e for e in shop_wares(pb) if abs(pb.memory[e + 3] - x) < 8), None)


def coins(pb):
    return pb.memory[PL + PL_COINS] | pb.memory[PL + PL_COINS + 1] << 8


def set_coins(pb, value):
    put16(pb, PL + PL_COINS, value)


def touch(pb, x, y):
    """Step onto a shelf the way test_merchant_stock does, then step off."""
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, max(0, y - 8))
    pb.memory[PL + PL_IFRAMES] = 120
    for _ in range(24):
        pb.tick()
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 104)
    for _ in range(40):
        pb.tick()


SCREEN = addr("_loop_current_screen")


def dismiss(pb, gif=None, frames=150):
    """Settle a room entry; page through any companion/vignette card."""
    for frame in range(600):
        if pb.memory[SCREEN] != 5 and frame % 20 == 0:
            pb.button_press("a")
        elif frame % 20 == 4:
            pb.button_release("a")
        pb.tick()
        if pb.memory[SCREEN] == 5:
            frames -= 1
            if gif is not None and frame % 3 == 0:
                gif.append(pb.screen.image.copy())
            if frames <= 0:
                break
    pb.button_release("a")
    assert pb.memory[SCREEN] == 5, f"stuck on screen {pb.memory[SCREEN]}"


def tile(tiles, x, y):
    return tiles[y * 20 + x]


def body_reach(tiles, start, goal):
    """2x2 body flood (reachable_exits rules) from start to goal."""
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}

    def ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16
                and all(tile(tiles, tx, ty) in walkable
                        for tx, ty in ((x - 1, y - 1), (x, y - 1),
                                       (x - 1, y), (x, y))))
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        if (x, y) == goal:
            return True
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if (nx, ny) not in seen and ok(nx, ny):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return False


def calm_room(pb):
    for i in range(32):
        e = EN + i * ENTITY_SIZE
        if pb.memory[e] == 2:
            pb.memory[e + 1] = 0


def reveal_stone(pb):
    """STONE: the ordinary cairn shoves north and the wall behind it opens."""
    calm_room(pb)
    put16(pb, PL + 9, 48)
    put16(pb, PL + 11, 64)
    pb.button_press("up")
    for _ in range(60):
        pb.tick()
        if pb.memory[KIND] == 0:
            break
    pb.button_release("up")
    for _ in range(10):
        pb.tick()
    assert pb.memory[KIND] == 0, "the Veil cairn did not move"
    assert pb.memory[TM + 6] == pb.memory[TM + 7] == BGT_DOOR, (
        "STONE mouth did not open behind the cairn")
    assert pb.memory[RS + RS_SHOP] & SHOP_MOUTH


def reveal_walk(pb):
    """THICKET: the marked wall is a walk-through; stepping in finds the vault."""
    calm_room(pb)
    x, y = pb.memory[SX], pb.memory[SY]
    if y == 0:
        put16(pb, PL + 9, x * 8)
        put16(pb, PL + 11, 2)
        button = "up"
    else:
        put16(pb, PL + 9, 2)
        put16(pb, PL + 11, y * 8 - 4)
        button = "left"
    pb.button_press(button)
    for _ in range(120):
        pb.tick()
        if pb.memory[RS + 13] == 2:
            break
    pb.button_release(button)
    assert pb.memory[RS + 13] == 2, "the THICKET wall did not admit the hero"
    dismiss(pb)
    assert len(shop_wares(pb)) == 3, "THICKET vault has no stall"
    assert pb.memory[RS + RS_SHOP] & SHOP_FOUND


def check_graph():
    for seed in SEEDS:
        for stage in range(9):
            host = mirror_host(seed, stage)
            assert host is not None, f"no Veil host stage={stage} seed={seed:#x}"
            assert graph_reachable(seed, stage, host), (
                f"Veil host {host} unreachable stage={stage} seed={seed:#x}")
    print("[secret-merchants] graph: one reachable role-free host per stage x "
          f"{len(SEEDS)} seeds")


def check_host_rooms(seed):
    shots = {}
    for stage in range(9):
        host = mirror_host(seed, stage)
        kind = VEIL_KIND[stage]
        seen = {}

        def probe(pb, tiles, stage=stage, host=host, kind=kind, seen=seen):
            assert pb.memory[HOST_HERE] == 1, f"stage {stage} cell {host} not host"
            assert pb.memory[HOST_CACHE] == host, (
                f"ROM host {pb.memory[HOST_CACHE]} != mirror {host}")
            assert pb.memory[KIND] == HIDDEN_FOR[kind], (
                f"stage {stage} tell kind {pb.memory[KIND]}")
            assert not shop_wares(pb), "a Veil ware sits in the open host room"
            assert not pb.memory[RS + RS_SHOP] & SHOP_MOUTH
            if kind == STONE:
                assert tile(tiles, 6, 6) == BGT_BLOCK, "cairn missing"
                assert tile(tiles, 6, 0) == tile(tiles, 7, 0) == BGT_WALL, (
                    "STONE mouth visible before the shove")
                goal = (7, 9)
            else:
                x, y = pb.memory[SX], pb.memory[SY]
                x2, y2 = pb.memory[SX2], pb.memory[SY2]
                assert tile(tiles, x, y) == tile(tiles, x2, y2) == BGT_WALL, (
                    f"stage {stage} mouth not concealed")
                assert (y == 0 and y2 == 0 and x2 == x + 1) or (
                    x == 0 and x2 == 0 and y2 == y + 1), "mouth not on a border"
                goal = (x + 1, 2) if y == 0 else (2, y + 1)
            assert body_reach(tiles, (10, 9), goal), (
                f"stage {stage} tell unreachable from the trail crossing")
            exits = reachable_exits(tiles, (10, 9))
            want = expected_graph_exits(stage, host, seed)
            assert want <= exits, (
                f"stage {stage} host lost graph exits {want - exits}")
            seen["ok"] = True
            if stage in (0, 1, 3):
                shots[stage] = pb.screen.image.copy()
            if stage == 3:
                reveal_stone(pb)
            elif stage == 1:
                reveal_walk(pb)

        generated_room(stage, seed, local_room=host, probe=probe)
        assert seen.get("ok"), f"stage {stage} probe did not run"
    for stage, image in shots.items():
        save(f"veil_host_stage{stage + 1}_hidden.png", image)
    print(f"[secret-merchants] host rooms: 9/9 concealed, reachable, solvable "
          f"(seed {seed:#x})")


def check_non_host(seed):
    stage = 0
    host = mirror_host(seed, stage)
    size = dungeon_size(stage)
    roles = set(mission_graph(size, seed, stage)["sequence"])
    other = next(c for c in range(1, size - 3)
                 if c != host and c not in roles and c not in RESERVED
                 and c != dungeon_entry_cell(size, seed, stage))

    def probe(pb, _tiles):
        assert pb.memory[HOST_HERE] == 0, f"cell {other} also claims the vault"
        assert not shop_wares(pb)
    generated_room(stage, seed, local_room=other, probe=probe)


def check_reveal_and_shop(seed):
    stage = 0
    host = mirror_host(seed, stage)
    pb = generated_room(stage, seed, local_room=host, keep_running=True)
    for i in range(32):   # keep the stage quiet for a clean recording
        e = EN + i * ENTITY_SIZE
        if pb.memory[e] == 2:
            pb.memory[e + 1] = 0
    x, y = pb.memory[SX], pb.memory[SY]
    north = (y == 0)
    if north:
        px, py, button, facing = x * 8, 16, "up", 0
    else:
        px, py, button, facing = 8, y * 8 - 4, "left", 3
    put16(pb, PL + 9, px)
    put16(pb, PL + 11, py)
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.button_press(button)
    for _ in range(4):
        pb.tick()
    pb.button_release(button)
    for _ in range(20):
        pb.tick()
    gif = [pb.screen.image.copy()]
    save("veil_reveal_1_before.png", gif[0])
    for frame in range(240):
        if frame % 12 == 0:
            pb.button_press("a")
        elif frame % 12 == 3:
            pb.button_release("a")
        pb.tick()
        if frame % 3 == 0:
            gif.append(pb.screen.image.copy())
        if pb.memory[KIND] == 0:
            break
    pb.button_release("a")
    assert pb.memory[KIND] == 0, (
        f"player fire did not open the BLAST tell at ({x},{y}) from "
        f"({px},{py}) facing {pb.memory[PL + PL_FACING]}")
    for _ in range(12):
        for _ in range(3):
            pb.tick()
        gif.append(pb.screen.image.copy())
    t = lambda tx, ty: pb.memory[TM + ty * 20 + tx]
    if north:
        assert t(x, 0) == t(x + 1, 0) == BGT_DOOR, "mouth did not open"
    else:
        assert t(0, y) == t(0, y + 1) == BGT_DOOR, "mouth did not open"
    assert pb.memory[RS + RS_SHOP] & SHOP_MOUTH, "opened mouth not persisted"
    save("veil_reveal_2_open.png", pb.screen.image)

    # Walk through the mouth into the vault stall.
    pb.button_press(button)
    for frame in range(240):
        pb.tick()
        if frame % 3 == 0 and pb.memory[SCREEN] == 5:
            gif.append(pb.screen.image.copy())
        if pb.memory[RS + 13] == 2:
            break
    pb.button_release(button)
    assert pb.memory[RS + 13] == 2, "the open mouth did not lead to the vault"
    dismiss(pb, gif)
    save_gif("veil_reveal.gif", gif)
    wares = shop_wares(pb)
    assert len(wares) == 3, f"vault stall has {len(wares)} wares"
    assert pb.memory[RS + RS_SHOP] & SHOP_FOUND, "vault discovery not recorded"
    prices = sorted((pb.memory[e + 3], pb.memory[e + 19]) for e in wares)
    assert [p for _, p in prices] == [TONIC_PRICE[0], 24, CHARM_PRICE[0]], prices
    for i in range(32):
        e = EN + i * ENTITY_SIZE
        if pb.memory[e] == 2:
            pb.memory[e + 1] = 0
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 104)
    for _ in range(60):
        pb.tick()
    save("veil_shop.png", pb.screen.image)
    shop_gif = [pb.screen.image.copy()]

    def buy(x, label):
        e = ware_at(pb, x)
        assert e is not None, f"no {label} shelf at x={x}"
        ex, ey = pb.memory[e + 3], pb.memory[e + 7]
        put16(pb, PL + 9, ex)
        put16(pb, PL + 11, max(0, ey - 8))
        pb.memory[PL + PL_IFRAMES] = 120
        for f in range(24):
            pb.tick()
            if f % 4 == 0:
                shop_gif.append(pb.screen.image.copy())
        put16(pb, PL + 9, 80)
        put16(pb, PL + 11, 104)
        for f in range(40):
            pb.tick()
            if f % 4 == 0:
                shop_gif.append(pb.screen.image.copy())

    # Short purse: nothing changes hands.
    set_coins(pb, 5)
    pb.memory[PL + PL_HP] = max(1, pb.memory[PL + PL_HPMAX] - 4)
    hp0 = pb.memory[PL + PL_HP]
    buy(104, "charm")
    assert coins(pb) == 5 and not pb.memory[RS + RS_CHARMS] & 1, "sold on credit"

    set_coins(pb, 200)
    buy(56, "tonic")
    assert coins(pb) == 200 - TONIC_PRICE[0], f"tonic charged {200 - coins(pb)}"
    assert pb.memory[PL + PL_HP] > hp0, "tonic did not heal"
    assert ware_at(pb, 56) is not None, "tonics restock"
    # Full health: the tonic is refused for free.
    pb.memory[PL + PL_HP] = pb.memory[PL + PL_HPMAX]
    pb.memory[PL + 4] = pb.memory[PL + 3]
    before = coins(pb)
    buy(56, "tonic")
    assert coins(pb) == before, "a full-health tonic was charged"

    before = coins(pb)
    buy(80, "bottle")
    assert coins(pb) == before - 24, f"bottle charged {before - coins(pb)}"
    assert pb.memory[RS + RS_SHOP] & (SHOP_B | SHOP_ARMED) == SHOP_B | SHOP_ARMED
    assert ware_at(pb, 80) is None, "bottle shelf did not empty"

    before = coins(pb)
    buy(104, "charm")
    assert coins(pb) == before - CHARM_PRICE[0], f"charm charged {before - coins(pb)}"
    assert pb.memory[RS + RS_CHARMS] & 1, "Cave Light charm not owned"
    assert pb.memory[RS + RS_SHOP] & SHOP_C
    assert ware_at(pb, 104) is None, "charm shelf did not empty"
    save("veil_shop_after.png", pb.screen.image)
    save_gif("veil_shop.gif", shop_gif, 80)
    # Suspend inside the vault and cold boot: discoveries ride the save.
    want = pb.memory[RS + RS_SHOP] & (SHOP_FOUND | SHOP_MOUTH)
    ram = io.BytesIO(bytes(0x8000))
    for _ in range(4):
        pb.tick()
    pb.stop(save=True, ram_file=ram)
    ram.seek(0)
    pb = PyBoy(str(dens.ROM), window="null", cgb=True, ram_file=ram)
    for _ in range(240):
        pb.tick()
    pb.button("a")
    for _ in range(90):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "cold boot did not resume the vault"
    assert pb.memory[RS + RS_SHOP] & want == want, (
        f"vault discovery lost over a power cycle: {pb.memory[RS + RS_SHOP]:#x}")
    pb.stop(save=False)

    # The opened mouth persists for later visits (MOUTH bit in secret_shop).
    def reopen(pb, _addrs):
        pb.memory[RS + RS_SHOP] |= SHOP_MOUTH

    def probe(pb, tiles):
        assert pb.memory[HOST_HERE] == 1
        if north:
            assert tile(tiles, x, 0) == tile(tiles, x + 1, 0) == BGT_DOOR
        else:
            assert tile(tiles, 0, y) == tile(tiles, 0, y + 1) == BGT_DOOR
        assert pb.memory[KIND] == 0, "a found mouth re-armed its tell"
    generated_room(stage, seed, local_room=host, pre_cross=reopen, probe=probe)
    print("[secret-merchants] BLAST reveal, persistence, vault stall, "
          "tonic/bottle/charm purchases, refusals")


def cave_tiles(pb):
    return {(x, y): dens.wide_tile(pb, x, y)
            for y in range(CAVE_TY - 1, CAVE_TY + 4)
            for x in range(CAVE_TX - 2, CAVE_TX + 3)}


def check_caves():
    pb = PyBoy(str(dens.ROM), window="null", cgb=True)
    dens.enter_riftwild(pb)
    dens.teleport_field(pb, 2)   # any ordinary field stamps (and caches) caves
    fields = list(pb.memory[CAVE_FIELDS:CAVE_FIELDS + 3])
    kinds = list(pb.memory[CAVE_KINDS:CAVE_KINDS + 3])
    assert sorted(kinds) == [0, 1, 2], f"cave kinds {kinds}"
    for band, field in enumerate(fields):
        assert band * 12 <= field < band * 12 + 12, f"cave {band} field {field}"
        assert field not in EXCLUDED_FIELDS | DEN_FIELDS_R0, (
            f"cave {band} shares landmark/den field {field}")
    order = sorted(range(3), key=lambda i: kinds[i])   # STONE, BLAST, THICKET
    for i in order:
        field, kind = fields[i], kinds[i]
        dens.teleport_field(pb, field)
        dens.calm(pb)
        mouth = dens.wide_tile(pb, CAVE_TX, CAVE_TY)
        assert mouth != dens.PORTAL, f"cave {i} open before its verb"
        assert not shop_wares(pb), "cave ware in the open field"
        approach = {STONE: (CAVE_TX - 1, CAVE_TY), BLAST: (CAVE_TX, CAVE_TY + 1),
                    THICKET: (CAVE_TX, CAVE_TY + 1)}[kind]
        extra = (dens.wide_tile(pb, *approach),)
        assert dens.reachable(pb, approach, extra), (
            f"cave {i} tell approach {approach} unreachable")
        dens.snap(pb, {}, "x", CAVE_TX, CAVE_TY + 3)
        hidden = pb.screen.image.copy()
        gif = [hidden]
        if kind == BLAST:
            # Without the Glove (or a Sauran grip) the plug will not budge.
            pb.memory[PL + dens.PL_WAYGEAR] &= ~dens.GLOVE & 0xFF
            dens.feet_on(pb, CAVE_TX, CAVE_TY + 1)
            dens.hold(pb, "up", 60)
            assert dens.wide_tile(pb, CAVE_TX, CAVE_TY) != dens.PORTAL, \
                "BLAST plug opened by a bare shove"
            pb.memory[PL + dens.PL_WAYGEAR] |= dens.GLOVE
        if kind == STONE:
            dens.feet_on(pb, CAVE_TX - 1, CAVE_TY)
            button = "right"
        else:
            dens.feet_on(pb, CAVE_TX, CAVE_TY + 1)
            button = "up"
        dens.tick(pb, 20)
        pb.button_press(button)
        for step in range(120):
            pb.tick()
            if step % 3 == 0:
                gif.append(pb.screen.image.copy())
            if dens.wide_tile(pb, CAVE_TX, CAVE_TY) == dens.PORTAL:
                break
        pb.button_release(button)
        assert dens.wide_tile(pb, CAVE_TX, CAVE_TY) == dens.PORTAL, (
            f"cave {i} (kind {kind}) did not open; tiles {cave_tiles(pb)}")
        caves = int.from_bytes(bytes(pb.memory[RS + RS_CAVES:RS + RS_CAVES + 4]),
                               "little")
        assert caves & (1 << (3 + i)), "cave mouth not persisted"
        for _ in range(10):
            dens.tick(pb, 3)
            gif.append(pb.screen.image.copy())
        dens.feet_on(pb, CAVE_TX, CAVE_TY)
        for step in range(150):
            pb.tick()
            if step % 3 == 0:
                gif.append(pb.screen.image.copy())
        assert dens.ws(pb) == CAVE_BASE + i, f"cave {i} portal went to {dens.ws(pb)}"
        caves = int.from_bytes(bytes(pb.memory[RS + RS_CAVES:RS + RS_CAVES + 4]),
                               "little")
        assert caves & (1 << i), "cave discovery not recorded"
        wares = shop_wares(pb)
        assert ware_at(pb, 48) and ware_at(pb, 80), (
            f"cave {i} kind {kind} lacks tonic/bottle: "
            f"{[(pb.memory[e + 3], pb.memory[e + 7], pb.memory[e + 20]) for e in shop_wares(pb)]} "
            f"caves={bytes(pb.memory[RS + RS_CAVES:RS + RS_CAVES + 4]).hex()}")
        if kind != THICKET:   # THICKET's third shelf waits on chime / well state
            assert ware_at(pb, 112), f"cave {i} lacks its kind ware"
        pb.memory[PL + PL_HP] = max(1, pb.memory[PL + PL_HPMAX] - 4)
        set_coins(pb, 100)
        hp0 = pb.memory[PL + PL_HP]
        touch(pb, 48, 56)
        assert coins(pb) == 84 and pb.memory[PL + PL_HP] > hp0, (
            f"Rift Tonic purchase failed: coins={coins(pb)}")
        if True:
            save(f"cave_{['stone', 'blast', 'thicket'][kind]}_hidden.png", hidden)
            save(f"cave_{['stone', 'blast', 'thicket'][kind]}_shop.png",
                 pb.screen.image)
            save_gif(f"cave_{['stone', 'blast', 'thicket'][kind]}_reveal.gif", gif)
        # Way home: the stair returns to the field it was found in.
        dens.feet_on(pb, 3, 12)
        dens.tick(pb, 150)
        assert dens.ws(pb) == field, f"cave {i} stair went to {dens.ws(pb)}"
        assert dens.wide_tile(pb, CAVE_TX, CAVE_TY) == dens.PORTAL, "cave resealed"
    pb.stop(save=False)
    print("[secret-merchants] caves: 3/region, closed until their verb, "
          "reachable, stocked, way home")


def main():
    check_graph()
    check_host_rooms(SEEDS[0])
    check_non_host(SEEDS[0])
    check_reveal_and_shop(SEEDS[0])
    check_caves()
    print("[secret-merchants] PASS")


if __name__ == "__main__":
    main()
