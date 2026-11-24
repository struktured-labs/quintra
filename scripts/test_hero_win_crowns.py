#!/usr/bin/env python3
"""Live-ROM contract: per-hero win crowns, tiers, and meta SRAM compat."""
import io
import os
import re
import sys
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SRAM_SIZE = 32 * 1024
SCREEN_TITLE = 1
SCREEN_CLASS_SELECT = 2
SCREEN_INTRO = 4
SCREEN_ROOM = 5
SCREEN_VIGNETTE = 6
SCREEN_VICTORY = 12
HERO_SLOTS = 5
COUNT_COL = 12
SPR_CROWN_EASY = 20
SPR_CROWN_NORMAL = 21
SPR_CROWN_OBJ = 5
CS_PAL_OBJ_GOLD = 3
CS_PAL_OBJ_ROYAL = 4
DIFFICULTY_NORMAL = 0
DIFFICULTY_EASY = 1
RS_VICTORY = 10
RS_BOSSES = 11
RS_PENDING = 12
RS_DIFFICULTY = 26
PL_CLASS = 0
META_EXT = 13


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, SCREEN = map(
    addr, ("_run_state", "_player", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def meta_open(pb, bank=1):
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = bank


def meta_close(pb):
    pb.memory[0x0000] = 0


def meta_sum(data, start, end):
    return sum(data[start:end]) & 0xFF


def pack_tiers(tiers):
    bits = 0
    for i, tier in enumerate(tiers):
        bits |= (tier & 3) << (i * 2)
    return bits


def unpack_ext(pb):
    meta_open(pb, 1)
    raw = bytes(pb.memory[0xA000 + i] for i in range(23))
    total = pb.memory[0xA007] | (pb.memory[0xA008] << 8)
    runs = pb.memory[0xA005] | (pb.memory[0xA006] << 8)
    best = pb.memory[0xA003] | (pb.memory[0xA004] << 8)
    meta_close(pb)
    if len(raw) < 23 or raw[13:15] != b"C\x01" or raw[22] != meta_sum(raw, 13, 22):
        return best, runs, total, [0] * HERO_SLOTS, [0] * HERO_SLOTS, False
    bits = raw[20] | (raw[21] << 8)
    wins = list(raw[15:20])
    tiers = [(bits >> (i * 2)) & 3 for i in range(HERO_SLOTS)]
    return best, runs, total, wins, tiers, True


def write_legacy_meta(best=0, runs=0, wins=0, time=0xFFFF):
    """Pre-flags v2 record: checksum of [3..10] lives at [11].

    Lifetime trophies live in SRAM bank 1 (offset 0x2000 in the 32KB image).
    """
    rec = bytearray(SRAM_SIZE)
    b = 0x2000
    rec[b:b+3] = b"QM\x02"
    rec[b+3:b+5] = bytes((best & 0xFF, best >> 8))
    rec[b+5:b+7] = bytes((runs & 0xFF, runs >> 8))
    rec[b+7:b+9] = bytes((wins & 0xFF, wins >> 8))
    rec[b+9:b+11] = bytes((time & 0xFF, time >> 8))
    rec[b+11] = meta_sum(rec, b+3, b+11)
    return rec


def write_modern_meta(best=0, runs=0, wins=0, time=0xFFFF, flags=0,
                      hero_wins=None, hero_tiers=None):
    rec = bytearray(SRAM_SIZE)
    b = 0x2000
    rec[b:b+3] = b"QM\x02"
    rec[b+3:b+5] = bytes((best & 0xFF, best >> 8))
    rec[b+5:b+7] = bytes((runs & 0xFF, runs >> 8))
    rec[b+7:b+9] = bytes((wins & 0xFF, wins >> 8))
    rec[b+9:b+11] = bytes((time & 0xFF, time >> 8))
    rec[b+11] = flags
    rec[b+12] = meta_sum(rec, b, b+12)
    if hero_wins is not None:
        rec[b+13] = ord("C")
        rec[b+14] = 1
        for i, w in enumerate(hero_wins):
            rec[b+15 + i] = w
        bits = pack_tiers(hero_tiers or [0] * HERO_SLOTS)
        rec[b+20] = bits & 0xFF
        rec[b+21] = bits >> 8
        rec[b+22] = meta_sum(rec, b+13, b+22)
    return rec


def boot(ram=None):
    battery = io.BytesIO(bytes(ram) if ram is not None else bytes(SRAM_SIZE))
    pb = PyBoy(str(ROM), window="null", cgb=True, ram_file=battery)
    return pb


def wait_screen(pb, want, frames=240):
    for _ in range(frames):
        if pb.memory[SCREEN] == want:
            return
        pb.tick()
    raise AssertionError(f"timed out waiting for screen {want}, have {pb.memory[SCREEN]}")


def skip_to_title(pb):
    # Power-on plays the lore intro; START/A/B skip it, then the title
    # is the only place New Game (START) can open class select.
    for _ in range(600):
        if pb.memory[SCREEN] in (SCREEN_INTRO, SCREEN_TITLE):
            break
        pb.tick()
    if pb.memory[SCREEN] == SCREEN_INTRO:
        pb.tick(30)
        press(pb, "start")
    wait_screen(pb, SCREEN_TITLE, 2400)
    pb.tick(30)


def to_class_select(pb):
    skip_to_title(pb)
    press(pb, "start")
    wait_screen(pb, SCREEN_CLASS_SELECT, 200)
    # Attribute jobs 1-6 then palette bursts; let the page settle.
    pb.tick(90)


def to_room(pb, hero=0, easy=False):
    to_class_select(pb)
    for _ in range(hero):
        press(pb, "down")
        pb.tick(8)
    if easy:
        press(pb, "select")
        pb.tick(8)
    press(pb, "a")
    for _ in range(1200):
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
        pb.tick()
    assert pb.memory[SCREEN] == SCREEN_ROOM, pb.memory[SCREEN]
    assert pb.memory[PL + PL_CLASS] == hero, pb.memory[PL + PL_CLASS]
    # Let foyer fade / arrival holds finish so room_tick can see a win flag.
    pb.tick(60)


def trigger_victory(pb, difficulty=None):
    if difficulty is not None:
        pb.memory[RS + RS_DIFFICULTY] = difficulty
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[-1]
    pb.memory[RS + RS_VICTORY] = 1
    pb.memory[RS + RS_BOSSES] = 9
    pb.memory[RS + RS_PENDING] = 1
    if pb.memory[PL + 2] < 8:
        pb.memory[PL + 2] = 8
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_VICTORY:
            return
    raise AssertionError(f"did not enter victory, screen={pb.memory[SCREEN]}")


def tile_row(pb, row):
    base = 0x9800 + row * 32
    return [pb.memory[base + c] for c in range(20)]


def attr_row(pb, row):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 1
    base = 0x9800 + row * 32
    data = [pb.memory[base + c] for c in range(20)]
    pb.memory[0xFF4F] = bank
    return data


CS_PAL_GOLD = 1
CS_PAL_ROYAL = 4


def oam(pb, idx):
    base = 0xFE00 + idx * 4
    return tuple(pb.memory[base + k] for k in range(4))


def assert_no_head_crown(pb, label):
    y, x, tile, prop = oam(pb, SPR_CROWN_OBJ)
    assert y == 0 or x == 0, (
        f"{label}: unexpected head crown OAM y={y} x={x} tile={tile} prop={prop}"
    )


def assert_head_crown(pb, hero, tier, label):
    y, x, tile, prop = oam(pb, SPR_CROWN_OBJ)
    want = SPR_CROWN_NORMAL if tier >= 2 else SPR_CROWN_EASY
    pal = CS_PAL_OBJ_ROYAL if tier >= 2 else CS_PAL_OBJ_GOLD
    assert tile == want, f"{label}: head tile {tile} != {want} (y={y} x={x})"
    assert (prop & 7) == pal, f"{label}: head pal {prop & 7} != {pal}"
    py, px, _, _ = oam(pb, 0)
    assert py and px, f"{label}: preview missing ({px},{py})"
    # Exact per-hero offsets from class_select_crowns.c (must stay in sync).
    ox = (4, 4, 3, 4, 4)[hero]
    lift = (4, 4, 4, 4, 4)[hero]
    assert x == px + ox, f"{label}: crown x {x} != preview {px}+{ox}"
    assert y == py - lift, f"{label}: crown y {y} != preview {py}-{lift}"


def assert_no_crowns(pb, label):
    for i in range(HERO_SLOTS):
        row = tile_row(pb, 3 + i)
        blank = row[19]
        assert row[COUNT_COL] == blank, (
            f"{label}: unexpected count on hero {i}: {row}"
        )
    assert_no_head_crown(pb, label)


def assert_hero_crown(pb, hero, wins, tier, label, others_bare=False,
                      on_head=False):
    row = tile_row(pb, 3 + hero)
    digits = str(wins)
    first = row[COUNT_COL]
    base = first - int(digits[0])
    got = []
    for i, ch in enumerate(digits):
        got.append(row[COUNT_COL + i] - base)
    assert "".join(str(d) for d in got) == digits, (
        f"{label}: hero {hero} count tiles {got} != {digits} ({row})"
    )
    pal = CS_PAL_ROYAL if tier >= 2 else CS_PAL_GOLD
    attrs = attr_row(pb, 3 + hero)
    for i, _ in enumerate(digits):
        ap = attrs[COUNT_COL + i] & 7
        assert ap == pal, (
            f"{label}: hero {hero} digit {i} pal {ap} != {pal}"
        )
    if others_bare:
        for i in range(HERO_SLOTS):
            if i == hero:
                continue
            other = tile_row(pb, 3 + i)
            assert other[COUNT_COL] == other[19], (
                f"{label}: stray count on hero {i}: {other}"
            )
    if on_head:
        assert_head_crown(pb, hero, tier, label)
    else:
        # Selected hero with no wins hides the sprite; this helper does
        # not know the cursor, so callers check head state explicitly.
        pass


def capture(pb, path):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = pb.screen.image.convert("RGB").resize((320, 288), resample=0)
    img.save(dest)


def test_fresh_select():
    pb = boot()
    try:
        to_class_select(pb)
        assert_no_crowns(pb, "fresh")
        if os.environ.get("QUINTRA_CROWN_CAPTURE"):
            capture(pb, os.environ["QUINTRA_CROWN_CAPTURE"] + "/before-none.png")
    finally:
        pb.stop(save=False)


def test_injected_display():
    ram = write_modern_meta(
        wins=6,
        hero_wins=[0, 1, 12, 0, 3],
        hero_tiers=[0, 1, 2, 0, 2],
    )
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_no_head_crown(pb, "injected-wolfkin")
        assert tile_row(pb, 3)[COUNT_COL] == tile_row(pb, 3)[19]
        assert_hero_crown(pb, 1, 1, 1, "injected-sauran")
        assert_hero_crown(pb, 2, 12, 2, "injected-corvin")
        assert_hero_crown(pb, 4, 3, 2, "injected-vespine")
        assert tile_row(pb, 6)[COUNT_COL] == tile_row(pb, 6)[19]
        if os.environ.get("QUINTRA_CROWN_CAPTURE"):
            capture(pb, os.environ["QUINTRA_CROWN_CAPTURE"] + "/after-mixed.png")
    finally:
        pb.stop(save=False)


def test_record_once_per_hero_and_difficulty():
    # Wolfkin Normal win -> count 1, majestic crown.
    pb = boot()
    try:
        to_room(pb, hero=0, easy=False)
        assert pb.memory[RS + RS_DIFFICULTY] == DIFFICULTY_NORMAL
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert ok, "victory did not write the hero-crown extension"
        assert total >= 1
        assert wins == [1, 0, 0, 0, 0], wins
        assert tiers == [2, 0, 0, 0, 0], tiers
    finally:
        pb.stop(save=False)

    # Second Normal win as Wolfkin increments only Wolfkin.
    ram = write_modern_meta(
        runs=1, wins=1, flags=1,
        hero_wins=[1, 0, 0, 0, 0],
        hero_tiers=[2, 0, 0, 0, 0],
    )
    pb = boot(ram)
    try:
        to_room(pb, hero=0, easy=False)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert wins == [2, 0, 0, 0, 0], wins
        assert tiers == [2, 0, 0, 0, 0], tiers
        assert total >= 2
    finally:
        pb.stop(save=False)

    # Corvin Easy win is counted only on Corvin, simple crown.
    ram = write_modern_meta(
        runs=2, wins=2, flags=1,
        hero_wins=[2, 0, 0, 0, 0],
        hero_tiers=[2, 0, 0, 0, 0],
    )
    pb = boot(ram)
    try:
        to_room(pb, hero=2, easy=True)
        assert pb.memory[RS + RS_DIFFICULTY] == DIFFICULTY_EASY
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert wins == [2, 0, 1, 0, 0], wins
        assert tiers == [2, 0, 1, 0, 0], tiers
    finally:
        pb.stop(save=False)

    # Easy then Normal upgrades Picsean's crown; count increments once.
    ram = write_modern_meta(
        runs=3, wins=3, flags=1,
        hero_wins=[2, 0, 1, 1, 0],
        hero_tiers=[2, 0, 1, 1, 0],
    )
    pb = boot(ram)
    try:
        to_room(pb, hero=3, easy=False)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert wins == [2, 0, 1, 2, 0], wins
        assert tiers == [2, 0, 1, 2, 0], tiers
    finally:
        pb.stop(save=False)

    # Normal then Easy does not downgrade Sauran.
    ram = write_modern_meta(
        runs=4, wins=4, flags=1,
        hero_wins=[2, 1, 1, 2, 0],
        hero_tiers=[2, 2, 1, 2, 0],
    )
    pb = boot(ram)
    try:
        to_room(pb, hero=1, easy=True)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert wins == [2, 2, 1, 2, 0], wins
        assert tiers == [2, 2, 1, 2, 0], tiers
    finally:
        pb.stop(save=False)


def test_select_after_easy_and_normal():
    ram = write_modern_meta(
        wins=2,
        hero_wins=[1, 0, 0, 0, 1],
        hero_tiers=[1, 0, 0, 0, 2],
    )
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_hero_crown(pb, 0, 1, 1, "select-easy", on_head=True)
        assert_hero_crown(pb, 4, 1, 2, "select-vespine-count")
        if os.environ.get("QUINTRA_CROWN_CAPTURE"):
            base = os.environ["QUINTRA_CROWN_CAPTURE"]
            capture(pb, base + "/after-easy.png")
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(90)
            assert_hero_crown(pb, 4, 1, 2, "select-normal", on_head=True)
            capture(pb, base + "/after-normal.png")
        else:
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(8)
            press(pb, "down")
            pb.tick(90)
            assert_hero_crown(pb, 4, 1, 2, "select-normal", on_head=True)
    finally:
        pb.stop(save=False)


def test_legacy_meta_compat():
    ram = write_legacy_meta(best=120, runs=7, wins=4, time=400)
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_no_crowns(pb, "legacy")
        # Leave select and start a Wolfkin run so a win can migrate in place.
        press(pb, "a")
        for _ in range(1200):
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.tick(60)
        trigger_victory(pb, difficulty=DIFFICULTY_NORMAL)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert ok
        assert best == 120 or best >= 120
        assert total == 5, total
        assert runs == 8, runs
        assert wins == [1, 0, 0, 0, 0], wins
        assert tiers == [2, 0, 0, 0, 0], tiers
    finally:
        pb.stop(save=False)


def test_modern_meta_without_extension():
    ram = write_modern_meta(best=50, runs=3, wins=2, flags=1)
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_no_crowns(pb, "modern-no-ext")
        press(pb, "a")
        for _ in range(1200):
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.tick(60)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert ok
        assert best == 50 or best >= 50
        assert total == 3, total
        assert runs == 4, runs
        assert wins == [1, 0, 0, 0, 0], wins
    finally:
        pb.stop(save=False)


def test_hexa_is_not_a_hero_win():
    """The sixth colossus is a badge, not another per-hero crown increment."""
    ram = write_modern_meta(
        runs=1, wins=1, flags=1,
        hero_wins=[1, 0, 0, 0, 0],
        hero_tiers=[2, 0, 0, 0, 0],
    )
    pb = boot(ram)
    try:
        to_room(pb, hero=0, easy=False)
        # Hexa path: bosses_beaten == 10 and the sanctum bit in
        # dungeon_puzzles (offset 27). Set every bit so a mask shift
        # cannot miss the flag.
        pb.memory[RS + 1] = STAGE_BOSS_ROOM[-1]
        pb.memory[RS + RS_VICTORY] = 1
        pb.memory[RS + RS_BOSSES] = 10
        pb.memory[RS + RS_PENDING] = 1
        pb.memory[RS + 27] = 0xFF
        for _ in range(180):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_VICTORY:
                break
        assert pb.memory[SCREEN] == SCREEN_VICTORY, (
            f"hexa clear did not enter victory, screen={pb.memory[SCREEN]}"
        )
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert total == 1, total
        assert wins == [1, 0, 0, 0, 0], wins
    finally:
        pb.stop(save=False)


def test_saturation_and_three_digits():
    ram = write_modern_meta(
        wins=255,
        hero_wins=[255, 0, 0, 0, 0],
        hero_tiers=[2, 0, 0, 0, 0],
    )
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_hero_crown(pb, 0, 255, 2, "sat-display", others_bare=True,
                             on_head=True)
        row = tile_row(pb, 3)
        zero = row[COUNT_COL] - 2  # hundreds digit is '2'
        fourth = row[COUNT_COL + 3]
        assert not (0 <= (fourth - zero) <= 9), (
            f"sat-display: unexpected fourth digit tile {fourth:#x} ({row})"
        )
        # A further win must not wrap the count.
        press(pb, "a")
        for _ in range(1200):
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.tick(60)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert ok
        assert wins == [255, 0, 0, 0, 0], wins
        assert tiers == [2, 0, 0, 0, 0], tiers
    finally:
        pb.stop(save=False)


def test_corrupt_extension_is_not_corruption():
    ram = write_modern_meta(
        best=50, runs=3, wins=2, flags=1,
        hero_wins=[4, 0, 0, 0, 0],
        hero_tiers=[2, 0, 0, 0, 0],
    )
    # Break only the extension checksum; the QM totals must survive.
    ram[0x2000 + 22] ^= 0xFF
    pb = boot(ram)
    try:
        to_class_select(pb)
        assert_no_crowns(pb, "corrupt-ext")
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert not ok
        assert best == 50, best
        assert total == 2, total
        assert runs == 3, runs
        press(pb, "a")
        for _ in range(1200):
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.tick(60)
        trigger_victory(pb)
        best, runs, total, wins, tiers, ok = unpack_ext(pb)
        assert ok
        assert best == 50 or best >= 50
        assert total == 3, total
        assert runs == 4, runs
        assert wins == [1, 0, 0, 0, 0], wins
        assert tiers == [2, 0, 0, 0, 0], tiers
    finally:
        pb.stop(save=False)


def test_head_crown_gallery():
    """Capture each selected hero with a crown on the head (Easy 0-1, Normal 2-4)."""
    dest = os.environ.get("QUINTRA_CROWN_CAPTURE")
    ram = write_modern_meta(
        wins=5,
        hero_wins=[1, 1, 1, 1, 1],
        hero_tiers=[1, 1, 2, 2, 2],
    )
    pb = boot(ram)
    names = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
    tiers = (1, 1, 2, 2, 2)
    try:
        to_class_select(pb)
        for i, name in enumerate(names):
            if i:
                press(pb, "down")
                pb.tick(90)
            assert_hero_crown(pb, i, 1, tiers[i], f"gallery-{name}", on_head=True)
            if dest:
                capture(pb, dest + f"/select-{name}.png")
    finally:
        pb.stop(save=False)


def main():
    test_fresh_select()
    test_injected_display()
    test_record_once_per_hero_and_difficulty()
    test_select_after_easy_and_normal()
    test_head_crown_gallery()
    test_legacy_meta_compat()
    test_modern_meta_without_extension()
    test_hexa_is_not_a_hero_win()
    test_saturation_and_three_digits()
    test_corrupt_extension_is_not_corruption()
    print("[hero-win-crowns] PASS recording, tiers, display, and save compat")


if __name__ == "__main__":
    main()
