#!/usr/bin/env python3
"""Set pieces, 32-bit climate salt, and bank-1 tile art (wonder audit L2/A1-A3)."""
from collections import Counter

from PIL import Image, ImageDraw
from pyboy import PyBoy

from quintra_vignettes import mute_vignettes

from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, ORIGIN_X, ORIGIN_Y, PL, ROM, ROOT, RS, TM,
    WORLD_BOTTOM, WORLD_EXT, WORLD_H, WORLD_W, addr, exit_at, put16,
)
from test_riftwild_landmarks import (
    ROUTE, field_edges, wide_tiles, boot_world, cross_to,
)

# Ordinary fields only. Fixtures keep their authored layouts (setpiece.c).
FIXTURES = {1, 3, 5, 8, 16, 17, 21, 23, 27, 29, 30, 32, 34}
NONE = 0xFF
PIECE_COUNT = 14


# Region-0 den fields (riftwild_den.c den_field[0]).
DEN_FIELDS = {7, 14, 25}


def reserved(x, y, screen):
    """Mirror of riftwild_setpiece.c reserved(): the den clearing and its
    approach (carved after the set-piece pass) and field 0's landing."""
    if screen == 0 and y <= 6 and 6 <= x <= 13:
        return True
    if screen in DEN_FIELDS:
        if 19 <= x <= 28 and 17 <= y <= 27:
            return True
        if 8 <= x <= 11 and 10 <= y <= 23:
            return True
        if 8 <= x <= 21 and 20 <= y <= 23:
            return True
    return False


def symbols():
    return {
        "id": addr("_riftwild_setpiece_id"),
        "x": addr("_riftwild_setpiece_x"),
        "y": addr("_riftwild_setpiece_y"),
        "cache_x": addr("_riftwild_cache_x"),
        "cache_y": addr("_riftwild_cache_y"),
        "salt": addr("_riftwild_render_salt"),
        "stamp_n": addr("_rw_stamp_n"),
        "stamp_x": addr("_rw_stamp_x"),
        "stamp_y": addr("_rw_stamp_y"),
        "stamp_w": addr("_rw_stamp_w"),
        "stamp_h": addr("_rw_stamp_h"),
    }


def boot_seed(seed, bosses=1, hooks=()):
    """Same boss-exit fixture as the atlas, with a full 32-bit run seed.
    hooks: (symbol, callback) pairs registered before the Riftwild entry."""
    from quintra_topology import STAGE_BOSS_ROOM
    pb = PyBoy(str(ROM), window="null", cgb=True, sound_emulated=False)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    mute_vignettes(pb, ROM)
    for i in range(4):
        pb.memory[RS + 2 + i] = (seed >> (8 * i)) & 255
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[bosses - 1]
    pb.memory[RS + 11] = bosses
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[TM + 16 * 20 + 9] = 3
    pb.memory[TM + 16 * 20 + 10] = 3
    for name, fn in hooks:
        v = addr_banked(name)
        pb.hook_register(v >> 16, v & 0xFFFF, fn, None)
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0
    return pb


def piece_state(pb, sym):
    return (
        pb.memory[sym["id"]],
        pb.memory[sym["x"]],
        pb.memory[sym["y"]],
        pb.memory[sym["salt"]],
        pb.memory[sym["stamp_n"]],
        pb.memory[sym["cache_x"]],
        pb.memory[sym["cache_y"]],
    )


def assert_mouths(screen, wide):
    edges = field_edges(screen)
    if edges & 1:
        assert wide[0][7:13] == [36] * 6, \
            f"cell {screen} narrow north mouth: {wide[0][7:13]}"
    if edges & 2:
        mouth = [wide[y][30] for y in range(6, 12)]
        assert mouth == [36] * 6, f"cell {screen} narrow east mouth: {mouth}"
    if edges & 4:
        assert wide[30][7:13] == [36] * 6, \
            f"cell {screen} narrow south mouth: {wide[30][7:13]}"
    if edges & 8:
        mouth = [wide[y][0] for y in range(6, 12)]
        assert mouth == [36] * 6, f"cell {screen} narrow west mouth: {mouth}"


def walk_fields(pb, sym, shots=None):
    records = {}

    def snap(screen):
        wide = wide_tiles(pb)
        assert_mouths(screen, wide)
        st = piece_state(pb, sym)
        pid, x0, y0, salt, n, cx, cy = st
        if screen in FIXTURES:
            assert pid == NONE, f"fixture field {screen} has set piece {pid}"
        else:
            assert pid != NONE, f"ordinary field {screen} has no set piece"
            assert pid < PIECE_COUNT, pid
            # Stamp footprint stays off the hidden-den tell quadrants and
            # the field-0 landing apron.
            w = max(1, pb.memory[sym["stamp_w"]] if n else 1)
            h = max(1, pb.memory[sym["stamp_h"]] if n else 1)
            # Use the piece origin; stamps sit inside the piece.
            # A conservative box: 10x10 around the origin covers every template.
            for y in range(y0, y0 + 10):
                for x in range(x0, x0 + 10):
                    if reserved(x, y, screen):
                        # Only fail if this cell is actually inside a stamp.
                        hit = False
                        for i in range(n):
                            sx = pb.memory[sym["stamp_x"] + i]
                            sy = pb.memory[sym["stamp_y"] + i]
                            sw = pb.memory[sym["stamp_w"] + i]
                            sh = pb.memory[sym["stamp_h"] + i]
                            if sx <= x < sx + sw and sy <= y < sy + sh:
                                hit = True
                        assert not hit, (
                            f"field {screen} stamp overlaps reserved "
                            f"({x},{y}) piece={pid} at {x0},{y0}"
                        )
        records[screen] = {
            "id": pid, "x": x0, "y": y0, "salt": salt, "stamps": n,
            "cache": (cx, cy),
            "tiles": tuple(tile for row in wide for tile in row),
        }
        if shots is not None:
            for slot in range(32):
                base = EN + slot * 28
                pb.memory[base] = pb.memory[base + 1] = 0
            for _ in range(8):
                pb.tick()
            shots[screen] = pb.screen.image.copy()

    snap(0)
    for screen, x, y in ROUTE:
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        cross_to(pb, screen, x, y)
        if screen not in records:
            snap(screen)
    return records


def test_library_and_reserved():
    sym = symbols()
    pb = boot_seed(0x1234ABCD)
    shots = {}
    try:
        rec = walk_fields(pb, sym, shots)
    finally:
        pb.stop(save=False)
    assert set(rec) == set(range(36))
    ordinary = [s for s in rec if s not in FIXTURES]
    ids = [rec[s]["id"] for s in ordinary]
    assert all(i != NONE for i in ids), ids
    # Tight climate + the trail cross often only has room for a compact
    # fallback (the 3x3 shard). Large stamps still place when a pocket
    # exists; do not require a unique kind in every field.
    print("piece distribution", Counter(ids))
    sheet = Image.new("RGB", (6 * 160, 6 * 144), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for screen in range(36):
        x, y = (screen % 6) * 160, (screen // 6) * 144
        sheet.paste(shots[screen].convert("RGB"), (x, y))
        pid = rec[screen]["id"]
        label = "FIX" if screen in FIXTURES else f"P{pid}"
        draw.text((x + 2, y + 130), f"{screen:02d} {label}", fill=(255, 255, 255))
    out = ROOT / "tmp" / "riftwild-setpieces.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    return rec, out


def test_seed_bits_and_stability():
    """Same low byte, different high bytes must change the field (audit L3).
    The same 32-bit seed must redraw identically."""
    sym = symbols()
    # Low byte 0xCD in both; only the upper 24 bits differ.
    a, b = 0x1234ABCD, 0x00C0ABCD
    recs = []
    for seed in (a, a, b):
        pb = boot_seed(seed)
        try:
            # Field 0 is generated at boot; also walk to ordinary field 2.
            pb.memory[PL + 2] = pb.memory[PL + 1]
            pb.memory[PL + 15] = 120
            rec0 = piece_state(pb, sym) + (tuple(
                tile for row in wide_tiles(pb) for tile in row),)
            # Field 0's east mouth leads to fixture field 1; field 2 is
            # the next ordinary field along the same row.
            cross_to(pb, 1, 232, 60)
            cross_to(pb, 2, 232, 60)
            rec2 = piece_state(pb, sym) + (tuple(
                tile for row in wide_tiles(pb) for tile in row),)
        finally:
            pb.stop(save=False)
        recs.append((rec0, rec2))
    first_a, second_a, other = recs
    assert first_a == second_a, "same seed must be stable across boots"
    # Climate silhouettes and/or the set piece must move when high seed bits
    # change. Salt is the cheapest witness, the tile grid is the real one.
    assert first_a[0][3] != other[0][3] or first_a[0][7] != other[0][7] \
        or first_a[1][3] != other[1][3] or first_a[1][7] != other[1][7], (
        "high seed bits did not change field 0 or 2 "
        f"a={first_a[0][:5]} b={other[0][:5]}"
    )


def test_bank1_art_loaded():
    """riftwild_art_load() runs when a field is prepared, and an ordinary
    field carries a set piece whose stamps draw from that bank-1 art.

    PyBoy 2.7 exposes neither VRAM bank 1 nor CGB BG attributes, so the
    load is witnessed by an execution hook; the rendered art itself is
    reviewed in the field sheet this test writes."""
    sym = symbols()
    calls = []
    pb = boot_seed(0x1234ABCD, hooks=(
        ("_riftwild_art_load", lambda _: calls.append(1)),))
    try:
        assert calls, "riftwild_art_load did not run while preparing field 0"
        cross_to(pb, 1, 232, 60)
        cross_to(pb, 2, 232, 60)
        assert pb.memory[sym["id"]] != NONE, "field 2 has no set piece"
    finally:
        pb.stop(save=False)


def addr_banked(name):
    import re
    text = ROM.with_suffix(".noi").read_text()
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", text)
    assert m, name
    return int(m.group(1), 16)


def main():
    rec, sheet = test_library_and_reserved()
    test_seed_bits_and_stability()
    test_bank1_art_loaded()
    ordinary = [s for s in rec if s not in FIXTURES]
    kinds = {rec[s]['id'] for s in ordinary}
    large = [s for s in ordinary if rec[s]['id'] < 10]
    # Regression guard: a footprint rule that only accepts bare ground left
    # every field with the same 3x3 shard.
    assert len(kinds) >= 4, f"only {len(kinds)} set-piece kinds: {kinds}"
    assert len(large) >= 3, f"only {len(large)} fields fit a large piece"
    print(
        f"[riftwild-setpiece] PASS {len(ordinary)} ordinary fields, "
        f"{len(kinds)} piece kinds ({len(large)} large), "
        f"sheet {sheet}"
    )


if __name__ == "__main__":
    main()
