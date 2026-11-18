#!/usr/bin/env python3
"""Live-ROM contracts for the procedural dungeon puzzle families."""

import os
import re
import subprocess
from pathlib import Path

from quintra_topology import (
    STAGE_START, dungeon_direction, dungeon_predecessor, dungeon_size,
    mission_graph,
)
from make_stage_states import (
    boot_to_stage, cross_graph_edge, normalize_compact_source,
    select_rom_topology, symbol_addresses,
)
from test_stage_archetypes import generated_room

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

# Floor-note CH1 envelope: volume 15, decrease, period 3. Louder and
# slower than the old 0xA2 (vol 10, period 2) so each plate rings clearly.
RUNE_ENV = 0xF3
# Final accepted note: volume 15, decrease, period 7, so the pitch holds
# through the 40-frame delay before the reveal jingle takes CH1.
RUNE_ENV_FINAL = 0xF7
RUNE_ENV_ECHO = 0xF2


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def rune_addrs():
    """Symbols the shared stage-state helper does not currently export."""
    names = (
        "_room_rune_count", "_room_rune_x", "_room_rune_y", "_room_rune_pitch",
        "_room_rune_lit_mask", "_room_bg_origin_x", "_room_bg_origin_y",
        "_room_row_len", "_room_row_phrase", "_room_row_progress",
        "_room_echo_mode",
    )
    return {name: addr(name) for name in names}


RS, PL, EN, TM, KIND, LOCKED, COMBAT, WORLD_W, WORLD_H = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_puzzle_kind", "_room_puzzle_locked", "_room_combat_sealed",
    "_room_world_width", "_room_world_height",
))



# Rune-sequence pitch plates (BGT_NOTE_0..FLASH). A voiced plate flashes as
# BGT_NOTE_FLASH (121) with the door palette (3) for 8 frames, then restores.
BGT_NOTE_0, BGT_NOTE_LIT_0, BGT_NOTE_FLASH = 111, 116, 121
RUNE_FLASH_PAL = 3
RUNE_IDLE_TILE = (111, 112, 113, 114, 115)
RUNE_LIT_TILE = (116, 117, 118, 119, 120)
RUNE_NOTE_PAL = (2, 2, 2, 3, 3)  # crystal, crystal, crystal, door, door
# Packed BGR555 words, little-endian byte pairs, matching puzzle.c.
RUNE_PAL_LOW = (0x42, 0x10, 0x04, 0x71, 0x04, 0x63, 0x9F, 0x13)
RUNE_PAL_HIGH = (0x42, 0x10, 0x1F, 0x0A, 0x1C, 0x61, 0xFF, 0x6B)



def brighten_bgr555_bytes(lo, hi):
    """Match brighten_colour() in rune_notes.c: 60% of the way toward white."""
    colour = lo | (hi << 8)
    r, g, b = colour & 31, (colour >> 5) & 31, (colour >> 10) & 31
    r = r + (31 - r) * 3 // 5
    g = g + (31 - g) * 3 // 5
    b = b + (31 - b) * 3 // 5
    word = r | (g << 5) | (b << 10)
    return (word & 0xFF, word >> 8)


def palette_with_pressed(base, pressed_pitches, low=True):
    pal = list(base)
    for pitch in pressed_pitches:
        if low and pitch > 2:
            continue
        if not low and pitch < 3:
            continue
        i = 2 + (pitch * 2 if pitch <= 2 else (pitch - 3) * 2)
        pal[i], pal[i + 1] = brighten_bgr555_bytes(base[i], base[i + 1])
    return tuple(pal)


def is_rune_plate_tile(tile):
    return BGT_NOTE_0 <= tile <= BGT_NOTE_FLASH


def is_lit_plate(tile):
    return BGT_NOTE_LIT_0 <= tile <= (BGT_NOTE_LIT_0 + 4)


def find_rune_plates(pb):
    return [(x, y) for y in range(1, 16) for x in range(1, 19)
            if is_rune_plate_tile(pb.memory[TM + y * 20 + x])]


def room_tile_attr(pb, x, y, addrs, origin=None):
    """Read the on-screen CGB palette index for room tile (x, y)."""
    if origin is None:
        ox = pb.memory[addrs["_room_bg_origin_x"]]
        oy = pb.memory[addrs["_room_bg_origin_y"]]
    else:
        ox, oy = origin
    old = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 1
    attr = pb.memory[0x9800 + ((oy + y) & 31) * 32 + ((ox + x) & 31)] & 7
    pb.memory[0xFF4F] = old
    return attr


def cgb_bg_palette(pb, slot):
    result = []
    for offset in range(8):
        pb.memory[0xFF68] = slot * 8 + offset
        result.append(pb.memory[0xFF69])
    return tuple(result)


# Fill colour index each pitch's plate art draws with (bgt_note_a/b/c in
# rune_notes.c): pitches 0/3 use colour 1, 1/4 colour 2, 2 colour 3.
RUNE_FILL_INDEX = (1, 2, 3, 1, 2)


def bg_tile_pixels(pb, tile):
    """Decode BG tile `tile` (8800 addressing, VRAM bank 0) to colour indices."""
    base = (0x9000 + tile * 16) if tile < 128 else (0x8000 + tile * 16)
    raw = [pb.memory[0, base + i] for i in range(16)]
    pixels = []
    for row in range(8):
        lo, hi = raw[row * 2], raw[row * 2 + 1]
        for bit in range(7, -1, -1):
            pixels.append(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1))
    return pixels


def assert_plate_art(pb, tile, pitch, where=""):
    """The plate's VRAM art is the authored note tile, not stale/blank data.

    Regression for door entries that never uploaded tiles 111..121: plates
    rendered as solid outline-black squares, or as leftover Compass node
    art, until a pack resume reloaded them.
    """
    pixels = bg_tile_pixels(pb, tile)
    want = RUNE_FILL_INDEX[pitch]
    fill = pixels.count(want)
    stray = [c for c in pixels if c not in (0, want)]
    assert fill >= 16 and not stray, (
        f"plate {where} tile {tile} pitch {pitch}: VRAM art wrong "
        f"(fill colour {want} x{fill}, stray {sorted(set(stray))})")


def poison_plate_vram(pb):
    """Simulate stale Compass art left in the shared 111..121 slots."""
    for tile in range(BGT_NOTE_0, BGT_NOTE_FLASH + 1):
        for i in range(16):
            pb.memory[0, 0x9000 + tile * 16 + i] = 0xFF
    assert bg_tile_pixels(pb, BGT_NOTE_0) == [3] * 64, "VRAM poison did not stick"


def wait_rune_flash(pb):
    """Let the 8-frame white flash settle so lit/idle tiles can be sampled."""
    for _ in range(12):
        pb.tick()


def assert_note_colors(pb, addrs, expected_count):
    """Every visible plate uses a unique pitch colour from the fixed map."""
    count_addr = addrs["_room_rune_count"]
    xs = addrs["_room_rune_x"]
    ys = addrs["_room_rune_y"]
    pitches = addrs["_room_rune_pitch"]
    count = pb.memory[count_addr]
    assert count == expected_count, f"room_rune_count={count}, want {expected_count}"
    plates = find_rune_plates(pb)
    assert len(plates) == count, f"visible plates {plates} != count {count}"
    seen_pitch = []
    for i in range(count):
        x, y = pb.memory[xs + i], pb.memory[ys + i]
        pitch = pb.memory[pitches + i]
        tile = pb.memory[TM + y * 20 + x]
        assert 0 <= pitch <= 4, f"plate {i} pitch {pitch} out of range"
        assert pitch not in seen_pitch, f"pitch {pitch} used on two plates"
        seen_pitch.append(pitch)
        assert tile == RUNE_IDLE_TILE[pitch], (
            f"plate {i} at {(x, y)} pitch {pitch} tile {tile}, "
            f"want idle {RUNE_IDLE_TILE[pitch]}")
        assert_plate_art(pb, tile, pitch, (x, y))
        attr = room_tile_attr(pb, x, y, addrs)
        assert attr == RUNE_NOTE_PAL[pitch], (
            f"plate {i} at {(x, y)} pitch {pitch} pal {attr}, "
            f"want {RUNE_NOTE_PAL[pitch]}")
        assert (x, y) in plates
    pairs = [(RUNE_IDLE_TILE[p], RUNE_NOTE_PAL[p]) for p in seen_pitch]
    assert len(set(pairs)) == count, f"colour pairs collided: {pairs}"
    low = cgb_bg_palette(pb, 2)
    high = cgb_bg_palette(pb, 3)
    assert low == RUNE_PAL_LOW, f"crystal/note palette {low} != {RUNE_PAL_LOW}"
    assert high == RUNE_PAL_HIGH, f"door/note palette {high} != {RUNE_PAL_HIGH}"


def assert_flash_then_restore(pb, addrs, plate):
    """Stepping on a plate flashes white, then restores to idle or lit colour."""
    x, y = plate
    before = pb.memory[TM + y * 20 + x]
    feet_on(pb, x, y)
    flashed = False
    restored = None
    for _ in range(16):
        tile = pb.memory[TM + y * 20 + x]
        attr = room_tile_attr(pb, x, y, addrs)
        if tile == BGT_NOTE_FLASH and attr == RUNE_FLASH_PAL:
            flashed = True
        elif flashed:
            restored = tile
            break
        pb.tick()
    assert flashed, f"plate {plate} never flashed white after being voiced"
    assert restored == before or is_lit_plate(restored), (
        f"plate {plate} restored to unexpected tile {restored} (was {before})")
    wait_rune_flash(pb)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def cross_edge(pb, source_local, target_local):
    direction = dungeon_direction(source_local, target_local)
    x, y = {
        0: (72, 0),
        1: (pb.memory[WORLD_W] - 16, 60),
        2: (72, pb.memory[WORLD_H] - 16),
        3: (0, 60),
    }[direction]
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(180):
        pb.tick()


def load(stage, before_cross=None):
    stage_index = stage - 1
    seed = 0x51A6D00D
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    pb, _ram, _entry = boot_to_stage(ROM, addrs, stage_index, "normal", 0)
    if before_cross is not None:
        before_cross(pb)
    trial = mission_graph(
        dungeon_size(stage_index), seed, stage_index)["trial"]
    target = STAGE_START[stage_index] + trial
    if pb.memory[RS + 1] != target:
        # Cross a reciprocal live maze edge. The old shortcut painted a
        # portal into room_tilemap while the opening room used its 31x31
        # streamed backing store, so the engine correctly never saw it.
        source, direction_id = dungeon_predecessor(
            trial, dungeon_size(stage_index), seed, stage_index)
        pb.memory[RS + 1] = STAGE_START[stage_index] + source
        pb.memory[RS + 6] = 0xFF
        pb.memory[LOCKED] = 0
        pb.memory[COMBAT] = 0
        normalize_compact_source(pb, addrs)
        for i in range(32):
            ep = EN + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        direction = ("up", "right", "down", "left")[direction_id]
        cross_graph_edge(pb, PL, TM, direction)
        for _ in range(120):
            pb.tick()
            if pb.memory[RS + 1] == target:
                break
        pb.button_release(direction)
    assert pb.memory[RS + 1] == target
    for _ in range(90):
        pb.tick()
    return pb


def feet_on(pb, tx, ty):
    put16(pb, PL + 9, tx * 8 - 8)
    put16(pb, PL + 11, ty * 8 - 12)
    # Charge, the pitched clue, and the CH4 impact land a few frames after
    # the warp, and an APU envelope can already have decayed by a fixed
    # tick count. Record what was heard instead of sampling only the last
    # frame.
    heard_ch1, heard_ch4 = set(), set()
    for i in range(12):
        pb.tick()
        heard_ch1.add(pb.memory[0xFF12])
        heard_ch4.add(pb.memory[0xFF21])
        # Damage lands around tick 4 and the note on tick 5. Stop once the
        # note is still speaking so the final-rune hold can be measured.
        if i >= 4 and pb.memory[0xFF12] in (RUNE_ENV, RUNE_ENV_FINAL, RUNE_ENV_ECHO):
            break
    return heard_ch1, heard_ch4



def step_off(pb):
    feet_on(pb, 10, 13)


def active_hostiles(pb):
    return [i for i in range(32)
            if pb.memory[EN + i * 28] == 2
            and pb.memory[EN + i * 28 + 1] & 1]


def visible_hostiles(pb):
    return [i for i in active_hostiles(pb)
            if pb.memory[EN + i * 28 + 1] & 4]


def clear_hostiles(pb):
    for i in active_hostiles(pb):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0


def body_component(tiles, start):
    """Return compact-court cells reachable by the champion's 2x2 body."""
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}

    def body_ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16
                and all(tiles[ty * 20 + tx] in walkable
                        for tx, ty in ((x - 1, y - 1), (x, y - 1),
                                       (x - 1, y), (x, y))))

    seen, pending = {start}, [start]
    while pending:
        x, y = pending.pop()
        for cell in ((x, y - 1), (x + 1, y),
                     (x, y + 1), (x - 1, y)):
            if cell not in seen and body_ok(*cell):
                seen.add(cell)
                pending.append(cell)
    return seen


def push_seal_contract():
    pb = load(1)
    assert pb.memory[KIND] == 1 and pb.memory[LOCKED] == 1
    assert len(active_hostiles(pb)) >= 4, (
        "push puzzle did not retain its live guard pack")
    assert visible_hostiles(pb), "push puzzle looked empty on arrival"
    out = Path(os.environ.get("PUSH_SEAL_PREVIEW_DIR", ROOT / "tmp"))
    out.mkdir(parents=True, exist_ok=True)
    frames = [pb.screen.image.copy()]
    frames[-1].save(out / "push-seal-arrival.png")
    clear_hostiles(pb)  # isolate cairn mechanics after proving population
    for _ in range(8):
        pb.tick()
    frames.append(pb.screen.image.copy())
    frames[-1].save(out / "push-seal-socket.png")
    blocks = [(x, y) for y in range(1, 16) for x in range(1, 19)
              if pb.memory[TM + y * 20 + x] == 25]
    assert len(blocks) == 1, f"push seal needs one readable cairn, got {blocks}"
    sx, sy = pb.memory[addr("_room_socket_x")], pb.memory[addr("_room_socket_y")]
    assert (sx, sy) != (0xFF, 0xFF), "push seal has no gold socket"
    assert all(pb.memory[TM + (sy + dy) * 20 + sx + dx] == 20
               for dy in (0, 1) for dx in (0, 1)), "socket is not a 2x2 gold plate"
    assert blocks[0][0] != sx and blocks[0][1] != sy, (
        "socket must sit on an L route, not a straight shove")

    def cairn():
        return next((x, y) for y in range(1, 16) for x in range(1, 19)
                    if pb.memory[TM + y * 20 + x] == 25)

    def shove(direction):
        bx, by = cairn()
        hx, hy = {"right": (bx * 8 - 20, by * 8 - 8),
                  "left": ((bx + 2) * 8 + 4, by * 8 - 8),
                  "down": (bx * 8, by * 8 - 20),
                  "up": (bx * 8, (by + 2) * 8 + 4)}[direction]
        put16(pb, PL + 9, hx)
        put16(pb, PL + 11, hy)
        pb.button_press(direction)
        for _ in range(120):
            pb.tick()
            if cairn() != (bx, by) or not pb.memory[LOCKED]:
                break
        pb.button_release(direction)
        for _ in range(30):  # let the slide finish before the next setup
            pb.tick()
        assert cairn() != (bx, by), f"cairn at {bx},{by} would not move {direction}"

    shoves = 0
    while cairn()[0] != sx:
        shove("right" if cairn()[0] < sx else "left")
        shoves += 1
        if shoves == 1:
            assert pb.memory[LOCKED] == 1, "an off-socket shove released the seal"
            frames.append(pb.screen.image.copy())
            frames[-1].save(out / "push-seal-mid.png")
    while cairn()[1] != sy and pb.memory[LOCKED]:
        shove("down" if cairn()[1] < sy else "up")
        shoves += 1
    for _ in range(30):
        pb.tick()
    assert shoves >= 4, f"socket route was trivial ({shoves} shoves)"
    assert pb.memory[LOCKED] == 0, "seating the cairn on the socket did not release seal"
    frames.append(pb.screen.image.copy())
    frames[-1].save(out / "push-seal-solved.png")
    frames[0].save(out / "push-seal.gif", save_all=True, append_images=frames[1:],
                   duration=700, loop=0)
    assert pb.memory[RS + 27] & 1, "Trial solve did not persist its stable bit"
    # Large dungeon courts continue beyond the legacy 20x17 viewport. Door
    # release must target the real 31x31 perimeter; stamping the old south
    # edge at y=16 leaves two conspicuous gold door tiles in mid-room.
    if pb.memory[WORLD_H] > 17 * 8:
        interior_south = (pb.memory[TM + 16 * 20 + 9],
                          pb.memory[TM + 16 * 20 + 10])
        assert 3 not in interior_south, (
            f"push solve stamped a false interior south door: {interior_south}")
    if pb.memory[WORLD_W] > 20 * 8:
        interior_east = (pb.memory[TM + 8 * 20 + 19],
                         pb.memory[TM + 9 * 20 + 19])
        assert 3 not in interior_east, (
            f"push solve stamped a false interior east door: {interior_east}")
    pb.stop(save=False)


def solve_runes(pb, runes):
    """Discover a deterministic phrase through only its visible lit feedback."""
    prefix = []

    def lit(rune):
        x, y = rune
        return is_lit_plate(pb.memory[TM + y * 20 + x])

    while pb.memory[LOCKED] and len(prefix) < len(runes):
        found = None
        for candidate in runes:
            if candidate in prefix:
                continue
            # A wrong candidate clears every rune. Replay only the known
            # prefix, exactly as a player following the tones would.
            if prefix and not all(lit(rune) for rune in prefix):
                for rune in prefix:
                    feet_on(pb, *rune)
                    wait_rune_flash(pb)
                    step_off(pb)
            hp_before = pb.memory[PL + 2]
            heard_ch1, heard_ch4 = feet_on(pb, *candidate)
            # Count remaining sustain immediately. wait_rune_flash would burn
            # the slow envelope before this check, because the flash helper
            # was added on this branch.
            held_mid = 0
            held_final = 0
            nr10 = pb.memory[0xFF10]
            # Count mid-phrase 0xF3 or the longer 0xF7 final before the
            # ducked fanfare takes CH1 at frame 40+8.
            while (held_mid + held_final) < 80:
                env = pb.memory[0xFF12]
                if env == RUNE_ENV:
                    held_mid += 1
                elif env == RUNE_ENV_FINAL:
                    held_final += 1
                else:
                    break
                pb.tick()
            if pb.memory[LOCKED]:
                wait_rune_flash(pb)
            if not pb.memory[LOCKED] or all(lit(rune) for rune in (*prefix, candidate)):
                assert pb.memory[PL + 2] == hp_before, (
                    "correct rune damaged the champion"
                )
                if not pb.memory[LOCKED]:
                    # NR10 bit 7 is unused and reads back as 1 on the APU.
                    assert (nr10 & 0x7F) == 0x00, (
                        f"final rune grew a sweep: NR10=0x{nr10:02X}")
                    assert RUNE_ENV_FINAL in heard_ch1 or held_final, (
                        f"final note was cut off: heard={sorted(heard_ch1)}")
                    assert held_final >= 24, (
                        f"final rune lasted only {held_final} frames of 0xF7")
                    # Hold should outlast the old 20-frame delay. Then CH4
                    # breath (8 frames) and D4 (0xA4) take CH1.
                    if pb.memory[0xFF12] == RUNE_ENV_FINAL:
                        for _ in range(40):
                            pb.tick()
                            if pb.memory[0xFF12] != RUNE_ENV_FINAL:
                                break
                    for _ in range(16):
                        if pb.memory[0xFF12] in (0xC0, 0xA4):
                            break
                        pb.tick()
                    assert pb.memory[0xFF12] in (0xC0, 0xA4), (
                        f"puzzle fanfare did not follow the ducked final note: "
                        f"0x{pb.memory[0xFF12]:02X} after {held_final} frames")
                found = candidate
                prefix.append(candidate)
                if pb.memory[LOCKED]:
                    # Mid-phrase notes must outlast the old 8-frame music
                    # restore cut. The slow envelope keeps NR12 at 0xF3
                    # until the claim window is nearly done.
                    assert (nr10 & 0x7F) == 0x00, (
                        f"mid-phrase rune grew a sweep: NR10=0x{nr10:02X}")
                    assert held_mid >= 24, (
                        f"mid-phrase rune rang only {held_mid} frames"
                    )
                step_off(pb)
                if pb.memory[LOCKED]:
                    # Every accepted, visibly lit note is safe to cross while
                    # routing toward the rest of the phrase. It must neither
                    # hurt the champion nor clear the confirmed prefix.
                    for confirmed in prefix:
                        hp_before_revisit = pb.memory[PL + 2]
                        lit_before_revisit = tuple(lit(rune) for rune in prefix)
                        pb.memory[0xFF12] = 0
                        heard_ch1, _ = feet_on(pb, *confirmed)
                        wait_rune_flash(pb)
                        assert pb.memory[PL + 2] == hp_before_revisit, (
                            "revisiting a lit rune damaged the champion"
                        )
                        assert tuple(lit(rune) for rune in prefix) == lit_before_revisit, (
                            "revisiting a lit rune reset the confirmed phrase"
                        )
                        assert RUNE_ENV in heard_ch1, (
                            "lit rune did not retrigger its pitched clue: "
                            f"env=0x{pb.memory[0xFF12]:02X} heard={sorted(heard_ch1)} "
                            f"confirmed={confirmed} prefix={prefix}"
                        )
                        step_off(pb)
                break
            assert pb.memory[PL + 2] == hp_before - 1, (
                "wrong rune did not charge exactly one half-heart"
            )
            assert RUNE_ENV in heard_ch1, (
                f"wrong rune muted its pitched sequence hint: heard={sorted(heard_ch1)}"
            )
            assert 0xC1 in heard_ch4, (
                f"wrong rune lost its separate impact voice: heard={sorted(heard_ch4)}"
            )
            # This routine intentionally discovers the hidden order through
            # mistakes. Refill only its test vessel so later candidates can
            # verify the same live damage contract without dying mid-proof.
            pb.memory[PL + 2] = hp_before
            step_off(pb)
        assert found is not None, f"visible feedback exposed no next tone after {prefix}"
    assert not pb.memory[LOCKED], f"discovered phrase did not release seal: {prefix}"
    return prefix


def rune_scale_source_contract():
    """Prove the write-only APU pitch table and ordering in source.

    Game Boy frequency registers read back as open-bus values, so the live ROM
    contract above checks that every plate actually triggers CH1 while this
    check owns the exact rising/falling pitch relationship.
    """
    sfx = (ROOT / "src/audio/sfx.c").read_text()
    puzzle = (ROOT / "src/game/puzzle.c").read_text()
    match = re.search(r"static const u16 notes\[5\] = \{([^}]+)\}", sfx)
    assert match, "rune scale table disappeared"
    notes = [int(value) for value in re.findall(r"\d+", match.group(1))]
    assert len(notes) == 5 and all(a < b for a, b in zip(notes, notes[1:])), \
        f"rune degrees are not a rising scale: {notes}"
    assert "rune_count - 1 - order_rank" in puzzle, \
        "seeded descending traversal disappeared"
    assert "room_rune_pitch[rune_order[i]] = rune_pitch(i);" in puzzle, \
        "physical rune pitches are no longer stable by order rank"
    notes_c = (ROOT / "src/game/rune_notes.c").read_text()
    assert "sfx_play_rune(room_rune_pitch[plate]);" in notes_c, \
        "voiced plates no longer play their bound pitch"
    assert puzzle.count("voice_plate(touched);") >= 3, \
        "walk/wrong/revisit paths no longer voice the touched plate"
    rune = sfx.split("void sfx_play_rune", 1)[1].split("void sfx_tick", 1)[0]
    assert "ch1(0x00, 0x80, 0xF3, notes[step])" in rune, \
        "rune envelope is no longer volume 15 / decay period 3"
    assert "sfx_claim_channels(40, 0)" in rune, \
        "rune notes no longer hold CH1 for the slow decay"
    after = sfx.split("void sfx_play_puzzle_after_note", 1)[1].split(
        "void sfx_play_rune", 1)[0]
    assert "pend_timer = 40" in after, \
        "final-note fanfare delay is no longer 40 frames"
    assert "melody_lock(MELODY_PRIORITY_SECRET, 93)" in after, \
        "delayed fanfare is no longer locked against pickup voices"
    rune_final = (ROOT / "src/audio/sfx_rune.c").read_text()
    assert "rune_ch1(0xF7, rune_notes[step])" in rune_final, \
        "final rune envelope is no longer volume 15 / decay period 7"
    assert "sfx_claim_channels(56, 0)" in rune_final, \
        "final rune no longer reserves CH1 through the ducked jingle start"
    assert "sfx_play_puzzle_after_note()" in rune_final, \
        "final rune no longer schedules the ducked reveal jingle"
    assert "rune_ch1(0xF2, rune_notes[step])" in rune_final, \
        "echo notes no longer use the softer 0xF2 envelope"
    row = (ROOT / "src/game/rune_row.c").read_text()
    assert "row_echo_start(20)" in row, "Aether Lattice no longer echoes on entry"
    assert "sfx_play(SFX_HIT)" in row, "wrong row step no longer buzzes on CH4"
    assert "voice_plate_final(touched)" in row, "row solve no longer holds the last note"
    assert "voice_plate_final" in puzzle, "rune solve no longer holds the last note"




def assert_pressed_persists(pb, addrs):
    """A correct step stays sunken and brighter until a wrong note resets it."""
    count = pb.memory[addrs["_room_rune_count"]]
    xs = addrs["_room_rune_x"]
    ys = addrs["_room_rune_y"]
    pitches = addrs["_room_rune_pitch"]
    plates = [(pb.memory[xs + i], pb.memory[ys + i],
               pb.memory[pitches + i]) for i in range(count)]

    def plate_tile(plate):
        x, y, _ = plate
        return pb.memory[TM + y * 20 + x]

    def assert_idle_all():
        for x, y, pitch in plates:
            tile = pb.memory[TM + y * 20 + x]
            assert tile == RUNE_IDLE_TILE[pitch], (
                f"plate at {(x, y)} tile {tile} want idle {RUNE_IDLE_TILE[pitch]}")
            assert_plate_art(pb, tile, pitch, (x, y))
            attr = room_tile_attr(pb, x, y, addrs)
            assert attr == RUNE_NOTE_PAL[pitch], (
                f"plate at {(x, y)} pal {attr} want {RUNE_NOTE_PAL[pitch]}")
        low = cgb_bg_palette(pb, 2)
        high = cgb_bg_palette(pb, 3)
        assert low == RUNE_PAL_LOW, f"idle crystal palette {low} != {RUNE_PAL_LOW}"
        assert high == RUNE_PAL_HIGH, f"idle door palette {high} != {RUNE_PAL_HIGH}"

    def assert_latched(pressed):
        pressed_pitches = [p for _, _, p in pressed]
        for x, y, pitch in plates:
            want = (RUNE_LIT_TILE[pitch] if (x, y, pitch) in pressed
                    else RUNE_IDLE_TILE[pitch])
            tile = pb.memory[TM + y * 20 + x]
            assert tile == want, (
                f"plate at {(x, y)} pitch {pitch} tile {tile}, want {want}")
            assert_plate_art(pb, tile, pitch, (x, y))
            attr = room_tile_attr(pb, x, y, addrs)
            assert attr == RUNE_NOTE_PAL[pitch], (
                f"plate at {(x, y)} dropped pitch palette {attr}")
        want_low = palette_with_pressed(RUNE_PAL_LOW, pressed_pitches, True)
        want_high = palette_with_pressed(RUNE_PAL_HIGH, pressed_pitches, False)
        got_low = cgb_bg_palette(pb, 2)
        got_high = cgb_bg_palette(pb, 3)
        assert got_low == want_low, f"pressed crystal palette {got_low} != {want_low}"
        assert got_high == want_high, f"pressed door palette {got_high} != {want_high}"

    # Isolate the court: live guards can chip HP on a correct step and
    # make a latched plate look like a failed attempt. Park one inert
    # body so the room-clear jingle does not steal the APU either.
    guards = active_hostiles(pb)
    clear_hostiles(pb)
    if guards:
        ep = EN + guards[0] * 28
        pb.memory[ep] = 2
        pb.memory[ep + 1] = 0x01
        put16(pb, ep + 3, 8)
        put16(pb, ep + 7, 200)
        pb.memory[ep + 10] = pb.memory[ep + 11] = 0
    pb.memory[PL + 15] = 0  # drop leftover i-frames
    if pb.memory[PL + 2] < 2:
        pb.memory[PL + 2] = 6
    hp = pb.memory[PL + 2]
    assert_idle_all()
    confirmed = []
    for candidate in plates:
        for x, y, _ in confirmed:
            feet_on(pb, x, y)
            wait_rune_flash(pb)
        feet_on(pb, candidate[0], candidate[1])
        wait_rune_flash(pb)
        if is_lit_plate(plate_tile(candidate)) and pb.memory[PL + 2] == hp:
            confirmed.append(candidate)
            assert_latched(confirmed)
            step_off(pb)
            if len(confirmed) >= 1:
                break
        else:
            # This candidate was wrong; the court already reset to idle.
            hp = pb.memory[PL + 2]
            step_off(pb)
            assert_idle_all()
    assert confirmed, "could not latch a correct note for pressed-state"
    assert_latched(confirmed)

    wrong = next((p for p in plates if p not in confirmed), None)
    assert wrong is not None, "need a remaining plate to prove the reset"
    feet_on(pb, wrong[0], wrong[1])
    wait_rune_flash(pb)
    assert pb.memory[PL + 2] == hp - 1, "wrong note did not charge a half-heart"
    assert_idle_all()
    # Leave the court so the next contract can voice a plate; standing on a
    # rune keeps puzzle_contact latched and swallows the flash.
    step_off(pb)


def load_rune_room(stage_index, role):
    """Boot a specific Trial or Waystone rune-sequence room and keep PyBoy running."""
    seed = 0x51A6D00D
    cell = mission_graph(dungeon_size(stage_index), seed, stage_index)[role]
    from make_stage_states import symbol_addresses
    pb = generated_room(stage_index, seed=seed, local_room=cell, keep_running=True)
    addrs = {**symbol_addresses(ROM), **rune_addrs()}
    return pb, addrs


def rune_color_contract():
    """Each distinct pitch uses a distinct, stable CGB colour, even with sound off."""
    rune_scale_source_contract()
    from make_stage_states import symbol_addresses
    # All five authored pitch colours stay unique even when a live room only
    # uses three or four plates (Stages 3+ no longer assign rune phrases).
    assert len(set(zip(RUNE_IDLE_TILE, RUNE_NOTE_PAL))) == 5
    fills = (RUNE_PAL_LOW[2:4], RUNE_PAL_LOW[4:6], RUNE_PAL_LOW[6:8],
             RUNE_PAL_HIGH[2:4], RUNE_PAL_HIGH[4:6])
    assert len(set(fills)) == 5, f"packed pitch colours collided: {fills}"

    # Stage 2 Trial is a four-note phrase (load() path, same seed). It is
    # entered through a door, with the shared plate slots pre-filled with
    # stale art: the door path must upload the note tiles itself.
    pb = load(2, before_cross=poison_plate_vram)
    addrs = {**symbol_addresses(ROM), **rune_addrs()}
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1
    assert_note_colors(pb, addrs, 4)
    assert_pressed_persists(pb, addrs)
    runes = find_rune_plates(pb)
    assert_flash_then_restore(pb, addrs, runes[0])
    if pb.memory[LOCKED]:
        count = pb.memory[addrs["_room_rune_count"]]
        seen = set()
        for i in range(count):
            x = pb.memory[addrs["_room_rune_x"] + i]
            y = pb.memory[addrs["_room_rune_y"] + i]
            pitch = pb.memory[addrs["_room_rune_pitch"] + i]
            tile = pb.memory[TM + y * 20 + x]
            attr = room_tile_attr(pb, x, y, addrs)
            assert attr == RUNE_NOTE_PAL[pitch]
            assert tile in (RUNE_IDLE_TILE[pitch], RUNE_LIT_TILE[pitch])
            seen.add(pitch)
        assert len(seen) == count
    pb.stop(save=False)

    # Stage 1 Waystone is a three-note phrase for this seed.
    pb, addrs = load_rune_room(0, "waystone")
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1, (
        f"stage 1 waystone was kind={pb.memory[KIND]} locked={pb.memory[LOCKED]}")
    assert_note_colors(pb, addrs, 3)
    assert_pressed_persists(pb, addrs)
    pb.stop(save=False)


def rune_sequence_contract():
    rune_scale_source_contract()
    pb = load(2)
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1
    assert len(active_hostiles(pb)) >= 4, (
        "rune puzzle did not retain its live guard pack")
    assert visible_hostiles(pb), "rune puzzle looked empty on arrival"
    guards = active_hostiles(pb)
    clear_hostiles(pb)  # isolate note/damage mechanics after proving population
    # Zeroing every guard trips the room-clear jingle, which melody-locks
    # the APU and swallows the wrong-rune CH4 impact. Park one inert body
    # far from the court so the room stays "live." Drop leftover i-frames
    # from the approach so the first plate can charge a half-heart.
    ep = EN + guards[0] * 28
    pb.memory[ep] = 2
    pb.memory[ep + 1] = 0x01
    put16(pb, ep + 3, 8)
    put16(pb, ep + 7, 200)
    pb.memory[ep + 10] = pb.memory[ep + 11] = 0
    pb.memory[PL + 15] = 0
    runes = find_rune_plates(pb)
    assert len(runes) == 4, f"stage two needs four runes, got {runes}"
    assert max(x for x, _ in runes) - min(x for x, _ in runes) >= 12
    assert max(y for _, y in runes) - min(y for _, y in runes) >= 8
    order = solve_runes(pb, runes)
    assert len(order) == 4 and len(set(order)) == 4
    pb.stop(save=False)


def exit_to(pb, target, stage):
    source = pb.memory[RS + 1] - STAGE_START[stage]
    destination = target - STAGE_START[stage]
    cross_edge(pb, source, destination)
    # room_counter changes before the streamed slide and destination role
    # finish. Observe the completed room, not that intentional mid-slide
    # checkpoint exposed by PyBoy's per-VBlank scheduler.
    for _ in range(180):
        pb.tick()
        if pb.memory[KIND] == 4 and not (pb.memory[0xFF42] or pb.memory[0xFF43]):
            break


def late_depth_puzzle_contract():
    # Expanded dungeons spend their new depth on a second authored puzzle
    # beat. From Stage 3 on that Waystone is a Sun Lattice light puzzle.
    sun_lattice_contract(3, "waystone")


def wide_waystone_circuit_contract():
    # The fixed full-campaign world once produced a horizontal Stage 7 court
    # whose mandatory fixture sat on an isolated floor island. Its Waystone
    # is now a Sun Lattice: every vane on the light path must stay reachable
    # by a walking champion in that same wide court.
    stage = 6
    seed = 2064128163
    waystone = mission_graph(dungeon_size(stage), seed, stage)["waystone"]

    def probe(pb, tiles):
        assert pb.memory[KIND] == slh.PUZZLE_SUN_LATTICE and pb.memory[LOCKED] == 1
        assert len(active_hostiles(pb)) >= 5, \
            "late Waystone did not retain its scaled guard pack"
        assert visible_hostiles(pb), "late Waystone looked empty on arrival"
        fixtures = slh.read_state(pb, SL)
        sh, sv, _ = slh.trace(fixtures, [f["solved"] for f in fixtures])
        component = lattice_component(pb, tilemap(pb))
        for f in fixtures:
            if f["kind"] == slh.SLK_VANE and any(
                    (f["x"] + dx, f["y"] + dy) in (sh | sv)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                assert slh.melee_reachable(component, f["x"], f["y"]), (
                    f"wide-court Waystone marooned vane {(f['x'], f['y'])}")

    generated_room(stage, seed, local_room=waystone, probe=probe)


def opening_shop_is_not_a_puzzle():
    pb = load(1)
    # The merchant remains the generated footprint's size-3 service cell.
    target_local = dungeon_size(0) - 3
    target = STAGE_START[0] + target_local
    seed = sum(pb.memory[RS + 2 + i] << (8 * i) for i in range(4))
    source, _ = dungeon_predecessor(target_local, dungeon_size(0), seed, 0)
    pb.memory[RS + 1] = STAGE_START[0] + source
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[COMBAT] = 0
    pb.memory[LOCKED] = 0
    cross_edge(pb, source, target_local)
    for _ in range(60):
        pb.tick()
        if pb.memory[RS + 1] == target and pb.memory[KIND] == 0:
            break
    assert pb.memory[RS + 1] == target
    assert pb.memory[KIND] == 0 and pb.memory[LOCKED] == 0, \
        "opening shop collided with the late-depth puzzle role"
    pb.stop(save=False)


def deep_phase_contract():
    bit = 1 << 2

    def switch_probe(pb, _tiles, frames=None, echo_log=None):
        assert pb.memory[KIND] == 3 and pb.memory[LOCKED] == 0
        assert len(active_hostiles(pb)) >= 4, \
            "Aether Lattice did not retain its live guard pack"
        assert visible_hostiles(pb), "Aether Lattice looked empty on arrival"
        clear_hostiles(pb)
        assert not (pb.memory[RS + 28] & bit)
        addrs = rune_addrs()
        positions = ((4, 7), (8, 9), (12, 7), (16, 9))
        length = pb.memory[addrs["_room_row_len"]]
        phrase = tuple(pb.memory[addrs["_room_row_phrase"] + i]
                       for i in range(length))
        assert length in (3, 4, 5), f"unexpected row length {length}"
        # Stage 1 (bosses_beaten == 0) uses a 3-note phrase.
        assert length == 3, f"stage 1 Aether Lattice length {length}, want 3"
        assert phrase[0] != phrase[1], f"consecutive repeat in phrase {phrase}"
        assert phrase[:3] not in ((0, 1, 2), (3, 2, 1)), \
            f"phrase {phrase} is a banned left-to-right or right-to-left sweep"

        def snap():
            if frames is not None:
                frames.append(pb.screen.image.copy())

        def plate_tile(i):
            x, y = positions[i]
            return pb.memory[TM + y * 20 + x]

        def assert_row_notes(lit=False):
            for i, (x, y) in enumerate(positions):
                tile = plate_tile(i)
                want = RUNE_LIT_TILE[i] if lit else RUNE_IDLE_TILE[i]
                assert tile == want, (
                    f"plate {i} at {(x, y)} tile {tile}, want {want} lit={lit}")
                attr = room_tile_attr(pb, x, y, addrs)
                assert attr == RUNE_NOTE_PAL[i], (
                    f"plate {i} palette {attr}, want {RUNE_NOTE_PAL[i]}")
                assert_plate_art(pb, tile, i, (x, y))
            want_low = palette_with_pressed(RUNE_PAL_LOW, list(range(4)) if lit else [], True)
            want_high = palette_with_pressed(RUNE_PAL_HIGH, list(range(4)) if lit else [], False)
            assert cgb_bg_palette(pb, 2) == want_low, "row low palette"
            assert cgb_bg_palette(pb, 3) == want_high, "row high palette"

        def echo_mode():
            return pb.memory[addrs["_room_echo_mode"]]

        def plates_flashing():
            return any(pb.memory[TM + y * 20 + x] == BGT_NOTE_FLASH
                       for x, y in positions)

        def wait_plates_idle(budget=40):
            for _ in range(budget):
                if not plates_flashing():
                    return
                pb.tick()
                snap()
            assert False, (
                f"plates still flashing: "
                f"{[pb.memory[TM + y * 20 + x] for x, y in positions]}")

        def wait_echo_idle(budget=250):
            heard_ch1, flashes = set(), []
            # Drain a leftover flash even when the echo state machine is idle.
            for _ in range(16):
                if echo_mode() == 0 and not plates_flashing():
                    break
                pb.tick()
            for _ in range(budget):
                if echo_mode() == 0 and not heard_ch1 and not flashes and not plates_flashing():
                    # Already idle with nothing recorded this wait: done.
                    return heard_ch1, flashes
                env = pb.memory[0xFF12]
                heard_ch1.add(env)
                for i, (x, y) in enumerate(positions):
                    if pb.memory[TM + y * 20 + x] == BGT_NOTE_FLASH:
                        if i not in flashes:
                            flashes.append(i)
                if echo_mode() == 0 and flashes and not plates_flashing():
                    snap()
                    return heard_ch1, flashes
                pb.tick()
                snap()
            assert False, (
                f"echo never finished: mode={echo_mode()} heard={heard_ch1} "
                f"flashes={flashes}")

        # Entry echo was recorded by the wrapping wait, if provided.
        if echo_log is not None:
            assert echo_log.get("echo_seen") or echo_log.get("flashes"), (
                f"Aether Lattice did not echo its phrase on entry: {echo_log}")
            assert RUNE_ENV_ECHO in echo_log.get("envs", set()) or echo_log.get("flashes"), (
                f"entry echo had no 0xF2 envelope: {echo_log}")
        # Park off the row before asserting idle art: an arrival that ends
        # on a plate would voice it the moment the entry echo finishes.
        step_off(pb)
        wait_rune_flash(pb)
        heard, flashes = wait_echo_idle()
        assert_row_notes(lit=False)
        # Mid-phrase work must not latch sunken tiles; only a solved row does.
        assert pb.memory[addrs["_room_rune_lit_mask"]] == 0

        def step_plate(i):
            x, y = positions[i]
            heard_ch1, heard_ch4 = feet_on(pb, x, y)
            snap()
            return heard_ch1, heard_ch4

        # A left-to-right or right-to-left mash must not open the gate.
        # Fast presses after a wrong step land during the re-echo and are ignored.
        for order, label in ((range(4), "L-R"), (range(3, -1, -1), "R-L")):
            wait_echo_idle()
            assert_row_notes(lit=False)
            for i in order:
                step_plate(i)
                # Only a few frames — do not wait out a 40-frame re-echo rest.
                for _ in range(6):
                    pb.tick()
            for _ in range(8):
                pb.tick()
            assert not (pb.memory[RS + 28] & bit), \
                f"{label} mash solved the row: phrase={phrase} progress={pb.memory[addrs['_room_row_progress']]}"
            # Let a mid-mash re-echo finish so the next trial starts clean.
            wait_echo_idle()
            pb.memory[addrs["_room_row_progress"]] = 0
            # Park off any plate so the next contact can arm.
            step_off(pb)

        # A deliberate wrong first step voices the plate, buzzes CH4, and re-echoes.
        wait_echo_idle()
        wrong = next(i for i in range(4) if i != phrase[0])
        heard_ch1, heard_ch4 = step_plate(wrong)
        assert RUNE_ENV in heard_ch1, (
            f"wrong step muted its pitch: heard={sorted(heard_ch1)}")
        # SFX_HIT writes NR42=0xC1; a slightly later tick may already decay it.
        assert 0xC1 in heard_ch4 or any(v & 0xF0 == 0xC0 for v in heard_ch4), (
            f"wrong step lost its CH4 buzz: heard={sorted(heard_ch4)}")
        assert pb.memory[addrs["_room_row_progress"]] == 0
        wait_plates_idle()
        step_off(pb)
        wait_plates_idle()
        assert_row_notes(lit=False)
        # Re-echo starts after a 40-frame rest; input is ignored until idle.
        reecho_started = False
        for _ in range(50):
            if echo_mode() != 0:
                reecho_started = True
                break
            pb.tick()
        assert reecho_started, "wrong step did not restart the phrase echo"
        heard, flashes = wait_echo_idle()
        assert RUNE_ENV_ECHO in heard or flashes, (
            f"re-echo was silent: heard={heard} flashes={flashes}")
        assert flashes == list(phrase) or not flashes or set(flashes) <= set(phrase), (
            f"re-echo flashed {flashes}, phrase is {phrase}")
        step_off(pb)

        # Walking the echoed phrase solves the row and holds the final note.
        wait_echo_idle()
        for index, plate in enumerate(phrase):
            heard_ch1, heard_ch4 = step_plate(plate)
            held_final = 0
            if index == len(phrase) - 1:
                while held_final < 80 and pb.memory[0xFF12] == RUNE_ENV_FINAL:
                    held_final += 1
                    pb.tick()
                assert RUNE_ENV_FINAL in heard_ch1 or held_final, (
                    f"row final note was cut off: heard={sorted(heard_ch1)}")
                assert held_final >= 24, (
                    f"row final note lasted only {held_final} frames")
                if pb.memory[0xFF12] == RUNE_ENV_FINAL:
                    for _ in range(40):
                        pb.tick()
                        if pb.memory[0xFF12] != RUNE_ENV_FINAL:
                            break
                for _ in range(16):
                    if pb.memory[0xFF12] in (0xC0, 0xA4):
                        break
                    pb.tick()
                assert pb.memory[0xFF12] in (0xC0, 0xA4), (
                    f"row fanfare did not follow the ducked final note: "
                    f"0x{pb.memory[0xFF12]:02X}")
                snap()
            else:
                assert RUNE_ENV in heard_ch1, (
                    f"correct mid step muted its pitch: heard={sorted(heard_ch1)}")
                wait_plates_idle()
                step_off(pb)
                wait_plates_idle()
                assert_row_notes(lit=False)
                assert pb.memory[addrs["_room_row_progress"]] == index + 1
                snap()
        assert pb.memory[RS + 28] & bit, \
            "solved deep Aether Lattice did not persist its remote phase bit"
        assert_row_notes(lit=True)
        step_off(pb)

        # Lightning zap closes the gate, resets the row, and re-echoes.
        # A second zap (after the re-echo) opens it again without walking.
        def zap_plate():
            # Retire leftover shots, then fire lightning at plate 0.
            for i in range(32 * 28):
                pb.memory[EN + i] = 0
            pb.tick(4)
            for i in range(32 * 28):
                pb.memory[EN + i] = 0
            x, y = positions[0]
            e = EN
            pb.memory[e] = 1
            pb.memory[e + 1] = 0x13
            put16(pb, e + 3, x * 8)
            put16(pb, e + 7, y * 8)
            pb.memory[e + 10] = 0
            pb.memory[e + 11] = 0
            pb.memory[e + 12] = 28
            pb.memory[e + 14] = 2
            pb.memory[e + 16] = 30
            pb.memory[e + 18] = 4  # lightning
            pb.memory[e + 19] = 0
            pb.memory[e + 25] = 0x77
            pb.memory[e + 26] = 2
            for _ in range(16):
                pb.tick()
            snap()

        zap_plate()
        assert not (pb.memory[RS + 28] & bit), "first zap did not close the remote gate"
        assert_row_notes(lit=False)
        assert pb.memory[addrs["_room_row_progress"]] == 0
        heard, flashes = wait_echo_idle()
        assert echo_mode() == 0
        assert RUNE_ENV_ECHO in heard or flashes, (
            f"zap close did not re-echo the phrase: heard={heard} flashes={flashes}")
        # Re-walk still solves after a zap reset.
        for index, plate in enumerate(phrase):
            step_plate(plate)
            if index < len(phrase) - 1:
                wait_rune_flash(pb)
                step_off(pb)
            else:
                for _ in range(60):
                    pb.tick()
        assert pb.memory[RS + 28] & bit, "re-echo + walk after zap did not re-solve"
        assert_row_notes(lit=True)
        step_off(pb)
        # Second close, then zap open without walking.
        zap_plate()
        assert not (pb.memory[RS + 28] & bit)
        wait_echo_idle()
        step_off(pb)
        zap_plate()
        assert pb.memory[RS + 28] & bit, "second zap did not reopen the remote gate"
        assert_row_notes(lit=True)
        pb.tick(20)

    def closed_gate_probe(pb, _tiles):
        assert pb.memory[KIND] == 4 and pb.memory[LOCKED] == 0
        assert len(active_hostiles(pb)) >= 4, \
            "closed phase gate did not retain its live guard pack"
        assert visible_hostiles(pb), "closed phase gate looked empty on arrival"
        assert all(pb.memory[TM + 11 * 20 + x] == 21 for x in range(4, 16))
        assert all(pb.memory[TM + 11 * 20 + x] != 21
                   for x in (2, 3, 16, 17)), \
            "closed deep wall lost its body-width anti-softlock detours"

    def open_gate_probe(pb, _tiles):
        assert pb.memory[KIND] == 4 and pb.memory[LOCKED] == 0
        assert len(active_hostiles(pb)) >= 4, \
            "open phase gate did not retain its live guard pack"
        assert visible_hostiles(pb), "open phase gate looked empty on arrival"
        assert all(pb.memory[TM + 11 * 20 + x] == 19 for x in range(4, 16))
        assert pb.memory[RS + 27] & (1 << 6), \
            "revisiting the opened mission gate did not persist its crossing"

    seed = 0xDEED1200
    graph = mission_graph(dungeon_size(0), seed, 0)
    # Entered through a door with the shared plate slots holding stale art:
    # the door path itself must upload the note tiles.
    echo_log = {"envs": set(), "flashes": [], "echo_seen": False, "modes": set()}
    gif_frames = []
    import test_stage_archetypes as tsa
    orig_wait = tsa.wait_for_generated_room

    def recording_wait(pb):
        previous = None
        stable = 0
        loaded = False
        from test_stage_archetypes import ROOM_W, ROOM_H
        for frame in range(480):
            pb.tick()
            mode = pb.memory[addr("_room_echo_mode")]
            echo_log["modes"].add(mode)
            if mode != 0:
                echo_log["echo_seen"] = True
            echo_log["envs"].add(pb.memory[0xFF12])
            for i, (x, y) in enumerate(((4, 7), (8, 9), (12, 7), (16, 9))):
                if pb.memory[TM + y * 20 + x] == BGT_NOTE_FLASH:
                    if i not in echo_log["flashes"]:
                        echo_log["flashes"].append(i)
            if frame % 4 == 0:
                gif_frames.append(pb.screen.image.copy())
            if not pb.memory[0xFF40] & 0x80:
                loaded = True
            if not loaded and frame < 150:
                continue
            tiles = bytes(pb.memory[TM + i] for i in range(ROOM_W * ROOM_H))
            lcd_on = bool(pb.memory[0xFF40] & 0x80)
            committed = not any(value & 0x80 for value in tiles)
            stable = stable + 1 if lcd_on and committed and tiles == previous else 0
            previous = tiles
            if stable >= 30:
                return list(tiles)
        raise AssertionError("room generation did not settle within 480 frames")

    tsa.wait_for_generated_room = recording_wait
    try:
        generated_room(
            0, seed, local_room=graph["deep_switch"],
            probe=lambda pb, tiles: switch_probe(pb, tiles, gif_frames, echo_log),
            pre_cross=lambda pb, _addrs: poison_plate_vram(pb))
    finally:
        tsa.wait_for_generated_room = orig_wait
    if gif_frames:
        from pathlib import Path as _P
        out = _P("/tmp/quintra-musicpz-gifs/aether-lattice-echo-solve.gif")
        out.parent.mkdir(parents=True, exist_ok=True)
        # Keep the file small: at most ~90 frames, 80ms each.
        step = max(1, len(gif_frames) // 90)
        slim = gif_frames[::step][:90]
        slim[0].save(out, save_all=True, append_images=slim[1:],
                     duration=80, loop=0)
    generated_room(0, seed, local_room=graph["deep_gate"], dungeon_phase=0,
                   probe=closed_gate_probe)
    generated_room(0, seed, local_room=graph["deep_gate"], dungeon_phase=bit,
                   probe=open_gate_probe)


# ---- Sun Lattice (PUZZLE_SUN_LATTICE, Stage 3+ Trial / Waystone) ----------

import sun_lattice_harness as slh  # noqa: E402

SL = slh.symbols(NOI)


def tilemap(pb):
    return [pb.memory[TM + i] for i in range(20 * 17)]


def lattice_beams_match(pb, fixtures):
    tiles = tilemap(pb)
    h = slh.read_bits(pb, SL["_sl_beam_h"])
    v = slh.read_bits(pb, SL["_sl_beam_v"])
    ph, pv, lit = slh.trace(fixtures, [f["ang"] for f in fixtures], tiles)
    assert (h, v) == (ph, pv), (
        f"ROM beam differs from reference trace: rom={sorted(h | v)} "
        f"ref={sorted(ph | pv)}")
    assert {i for i, f in enumerate(fixtures) if f["lit"]} == lit
    return h | v


def solve_sun_lattice(pb, frames=None):
    """Turn the room's vanes with real strikes until every Obelisk is lit.

    frames, when given, collects a screenshot after each strike.
    """
    def snap():
        if frames is not None:
            frames.append(pb.screen.image.copy())

    fixtures = slh.read_state(pb, SL)
    obelisks = {i for i, f in enumerate(fixtures) if f["kind"] == slh.SLK_OBELISK}
    lit = slh.trace(fixtures, [f["ang"] for f in fixtures], tilemap(pb))[2]
    assert not obelisks <= lit, "Sun Lattice spawned already lit"
    cx, cy = pb.memory[SL["_sl_crystal_x"]], pb.memory[SL["_sl_crystal_y"]]
    if cx != 0xFF and pb.memory[TM + cy * 20 + cx] == 22:
        hit = slh.strike(pb, PL, TM, cx, cy,
                         lambda: pb.memory[TM + cy * 20 + cx] != 22)
        assert hit, f"could not shatter the lattice crystal at {(cx, cy)}"
        for _ in range(10):
            pb.tick()
        snap()
        lattice_beams_match(pb, slh.read_state(pb, SL))
    # Replan after every strike: spread shots can graze a neighbouring vane,
    # exactly as they would for a player.
    turned = []
    for _ in range(16):
        if not pb.memory[LOCKED]:
            break
        fixtures = slh.read_state(pb, SL)
        plan = slh.solve(fixtures, tilemap(pb))
        assert plan is not None, f"no vane setting lights every Obelisk: {fixtures}"
        if not plan:
            for _ in range(30):
                pb.tick()
            continue
        i = plan[0]
        f = fixtures[i]
        before = pb.memory[SL["_sl_ang"] + i]
        hit = slh.strike(pb, PL, TM, f["x"], f["y"],
                         lambda: pb.memory[SL["_sl_ang"] + i] != before)
        assert hit, f"no strike could turn vane {i} at {(f['x'], f['y'])}"
        turned.append(i)
        for _ in range(10):   # past the 8-frame per-vane debounce
            pb.tick()
        snap()
        lattice_beams_match(pb, slh.read_state(pb, SL))
    plan = turned
    for _ in range(30):
        pb.tick()
        if not pb.memory[LOCKED]:
            break
    for _ in range(120):   # let the unlock fanfare settle
        pb.tick()
    snap()
    return plan


def enter_mission_cell(stage, role, seed=0x51A6D00D):
    """Boot the stage and cross a real maze edge into its Trial/Waystone."""
    stage_index = stage - 1
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    pb, _ram, _entry = boot_to_stage(ROM, addrs, stage_index, "normal", 0)
    run_seed = sum(pb.memory[RS + 2 + i] << (8 * i) for i in range(4))
    local = mission_graph(dungeon_size(stage_index), run_seed, stage_index)[role]
    target = STAGE_START[stage_index] + local
    if pb.memory[RS + 1] != target:
        source, direction_id = dungeon_predecessor(
            local, dungeon_size(stage_index), run_seed, stage_index)
        pb.memory[RS + 1] = STAGE_START[stage_index] + source
        pb.memory[RS + 6] = 0xFF
        pb.memory[LOCKED] = 0
        pb.memory[COMBAT] = 0
        normalize_compact_source(pb, addrs)
        for i in range(32):
            ep = EN + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        direction = ("up", "right", "down", "left")[direction_id]
        cross_graph_edge(pb, PL, TM, direction)
        for _ in range(120):
            pb.tick()
            if pb.memory[RS + 1] == target:
                break
        pb.button_release(direction)
    assert pb.memory[RS + 1] == target, f"could not enter stage {stage} {role}"
    for _ in range(90):
        pb.tick()
    return pb


def lattice_component(pb, tiles):
    """2x2-body cells reachable from where the champion entered."""
    px = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
    py = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
    fx, fy = min(19, max(1, (px + 8) >> 3)), min(16, max(1, (py + 12) >> 3))
    best = set()
    for sx in range(fx - 1, fx + 2):
        for sy in range(fy - 1, fy + 2):
            comp = slh.body_component(tiles, (sx, sy))
            if len(comp) > len(best):
                best = comp
    return best


def lattice_vram_contract(pb, fixtures):
    """Fixtures draw from VRAM bank 1 tiles 56..59, and survive the Pack
    and compass screens, which rebuild the room through room_draw_tilemap."""
    ox, oy = addr("_room_bg_origin_x"), addr("_room_bg_origin_y")
    expect = {slh.SLK_EMITTER: 56, slh.SLK_VANE: 57, slh.SLK_FIXED: 57,
              slh.SLK_BIFROST: 58, slh.SLK_OBELISK: 59}

    def cells():
        out = []
        for f in fixtures:
            a = (0x9800 + ((pb.memory[oy] + f["y"]) & 31) * 32
                 + ((pb.memory[ox] + f["x"]) & 31))
            out.append((pb.memory[0, a], pb.memory[1, a]))
        return out

    for (tile, attr), f in zip(cells(), fixtures):
        assert tile == expect[f["kind"]] and attr & 0x08, (
            f"fixture {f} drew tile {tile} attr {attr:#x}")
        if f["kind"] in (slh.SLK_VANE, slh.SLK_FIXED):
            assert bool(attr & 0x20) == bool(f["ang"]), "vane flip mismatch"
    before = cells()
    for button in ("start", "select"):
        for _ in range(2):
            pb.button_press(button)
            pb.tick()
            pb.button_release(button)
            for _ in range(60):
                pb.tick()
        assert cells() == before, f"{button} screen lost the lattice overlay"


SL_DUMP = Path(__file__).resolve().parent.parent / "target/release/sun-lattice-dump"


def lattice_rom_matches_rust(pb, fixtures, role):
    """The cart's SDCC build of sl_generate() must equal the Rust reference.

    The host parity script proves gcc and Rust agree; this closes the loop
    on the real ROM (SDCC u8/u16 promotion, banked call, live room seed).
    """
    if not SL_DUMP.exists():
        subprocess.run(["cargo", "build", "--release", "--locked", "-p",
                        "quintra-procgen", "--bin", "sun-lattice-dump"],
                       cwd=SL_DUMP.parents[2], check=True)
    run_seed = sum(pb.memory[RS + 2 + i] << (8 * i) for i in range(4))
    seed = (run_seed ^ (pb.memory[RS] << 16)
            ^ (pb.memory[RS + 1] * 0x9E3779B9)) & 0xFFFFFFFF
    bb = pb.memory[RS + 11]
    out = subprocess.run(
        [str(SL_DUMP), "--room", f"0x{seed:08x}", str(bb),
         "1" if role == "waystone" else "0"],
        check=True, capture_output=True, text=True).stdout.split()
    assert out[0] == f"{seed:08x}"
    assert int(out[1]) == pb.memory[SL["_sl_attempts"]], "attempts differ"
    rust = [tuple(map(int, t.split(","))) for t in out[3:]
            if t[0].isdigit()]
    rom = [(f["x"], f["y"], f["kind"], f["ang"], f["solved"]) for f in fixtures]
    assert rom == rust, f"ROM lattice differs from Rust:\n rom={rom}\nrust={rust}"
    crystal = next(t for t in out if t.startswith("C"))[1:]
    assert crystal == f"{pb.memory[SL['_sl_crystal_x']]},{pb.memory[SL['_sl_crystal_y']]}"
    plan = next(t for t in out if t.startswith("P"))[1:]
    py = slh.solve(fixtures, None)
    assert plan == ",".join(map(str, py)), f"solver parity: rust={plan} python={py}"
    return seed, len(py)


def sun_lattice_contract(stage, role="trial", gif=None):
    pb = enter_mission_cell(stage, role)
    bit = 1 if role == "trial" else 1 << 7
    assert pb.memory[KIND] == slh.PUZZLE_SUN_LATTICE, (
        f"stage {stage} {role} is kind {pb.memory[KIND]}, not Sun Lattice")
    assert pb.memory[LOCKED] == 1 and not (pb.memory[RS + 27] & bit)
    assert len(active_hostiles(pb)) >= 4, "lattice room lost its guard pack"
    clear_hostiles(pb)
    fixtures = slh.read_state(pb, SL)
    kinds = [f["kind"] for f in fixtures]
    assert kinds.count(slh.SLK_EMITTER) == 1 and slh.SLK_OBELISK in kinds
    if stage >= 4 and pb.memory[SL["_sl_attempts"]] != 0xFF:
        assert slh.SLK_BIFROST in kinds, "Frost Vault+ lattice lost its Wedge"
    seed, turns = lattice_rom_matches_rust(pb, fixtures, role)
    print(f"  stage {stage} {role}: room seed {seed:08x}, ROM == Rust, "
          f"{turns} turn(s)")
    tiles = tilemap(pb)
    # Every fixture is a solid 8x8 post in the collision map.
    assert all(tiles[f["y"] * 20 + f["x"]] == 21 for f in fixtures)
    # Spec question 4: each rotatable vane on the solved light path can be
    # struck in melee from dry floor the champion can actually walk to.
    component = lattice_component(pb, tiles)
    solved_h, solved_v, solved_lit = slh.trace(
        fixtures, [f["solved"] for f in fixtures])
    assert solved_lit == slh.obelisks(fixtures), "solved tree is not lit"
    on_path = set()
    for i, f in enumerate(fixtures):
        if f["kind"] == slh.SLK_VANE:
            neighbours = {(f["x"] + dx, f["y"] + dy)
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
            if neighbours & (solved_h | solved_v):
                on_path.add(i)
                assert slh.melee_reachable(component, f["x"], f["y"]), (
                    f"mandatory vane {i} at {(f['x'], f['y'])} is not "
                    f"melee-reachable from dry floor")
    assert on_path, "no rotatable vane on the light path"
    lattice_beams_match(pb, fixtures)
    for _ in range(60):   # let the arrival label and palette fade settle
        pb.tick()
    lattice_vram_contract(pb, fixtures)
    frames = [pb.screen.image.copy()] if gif is not None else None
    plan = solve_sun_lattice(pb, frames)
    assert pb.memory[LOCKED] == 0, f"lit lattice did not unlock: plan={plan}"
    assert pb.memory[RS + 27] & bit, "lattice solve did not persist its bit"
    fixtures = slh.read_state(pb, SL)
    assert all(f["lit"] for f in fixtures if f["kind"] == slh.SLK_OBELISK)
    # A solved room freezes its vanes: a further strike changes nothing.
    vane = next(i for i in on_path)
    before = pb.memory[SL["_sl_ang"] + vane]
    slh.strike(pb, PL, TM, fixtures[vane]["x"], fixtures[vane]["y"],
               lambda: pb.memory[SL["_sl_ang"] + vane] != before, frames=20)
    assert pb.memory[SL["_sl_ang"] + vane] == before, "solved vane still turns"
    if gif is not None:
        frames[0].save(gif, save_all=True, append_images=frames[1:],
                       duration=700, loop=0)
    pb.stop(save=False)
    return plan



def _parse_c_tile_bytes(src: Path, symbol: str) -> list[int]:
    text = src.read_text()
    match = re.search(
        rf"const u8 {re.escape(symbol)}\[16\]\s*=\s*\{{([^}}]+)\}}",
        text,
    )
    assert match, f"{symbol} disappeared from {src}"
    values = [int(token, 0) for token in re.findall(r"0x[0-9A-Fa-f]+", match.group(1))]
    assert len(values) == 16, f"{symbol} in {src} has {len(values)} bytes, want 16"
    return values


def door_switch_art_contract():
    """Pressed door-switch keeps a sunken plate and yields VRAM 122 to the map."""
    room = (ROOT / "src/game/room.c").read_text()
    assert "BGT_SWITCH_PRESSED, BGPAL_DOOR" in room, \
        "activate_switch no longer leaves a sunken door-switch plate"
    assert "BGT_FLOOR, BGPAL_FLOOR" not in room.split("static void activate_switch", 1)[1].split("room_open_secret", 1)[0], \
        "activate_switch still replaces the plate with floor"
    assert "tiles_load_switch_pressed()" in room, \
        "room_enter no longer reloads the sunken switch into VRAM 122"
    switch_c = (ROOT / "src/render/tiles_switch.c").read_text()
    assert "set_bkg_data(BGT_SWITCH_PRESSED, 1, bgt_switch_pressed)" in switch_c
    assert "#pragma bank 22" in switch_c
    world = (ROOT / "src/game/room_world.c").read_text()
    assert "BGT_SWITCH_PRESSED" in world
    pressed = _parse_c_tile_bytes(ROOT / "src/render/tiles_switch.c", "bgt_switch_pressed")
    unpressed = _parse_c_tile_bytes(ROOT / "src/render/sprites_gen.c", "bgt_switch")
    cache = _parse_c_tile_bytes(ROOT / "src/render/tiles_map.c", "bgt_map_cache")
    assert pressed != unpressed and pressed != cache
    assert len(pressed) == 16

    from make_stage_states import symbol_addresses
    pb = load(1)
    screen = addr("_loop_current_screen")
    player = PL
    vram = 0x9000 + 122 * 16

    def tile_vram():
        return [pb.memory[vram + i] for i in range(16)]

    assert tile_vram() == pressed, (
        f"room VRAM 122 is not the sunken switch: {tile_vram()} vs {pressed}")
    # SELECT loads the Compass cache glyph into the shared slot.
    pb.button_press("select")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == 8:
                for _ in range(90):
                    pb.tick()
                break
        else:
            raise AssertionError("SELECT did not open the Compass")
    finally:
        pb.button_release("select")
    assert tile_vram() == cache, (
        f"Compass did not overwrite VRAM 122 with the cache glyph: {tile_vram()}")
    pb.button_press("b")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == 5:
                break
        else:
            raise AssertionError("B did not return from the Compass")
    finally:
        pb.button_release("b")
    for _ in range(90):
        pb.memory[player + 2] = 14
        pb.memory[player + 15] = 60
        pb.tick()
    assert tile_vram() == pressed, (
        f"resume did not restore the sunken switch to VRAM 122: {tile_vram()}")
    pb.stop(save=False)


def main():
    push_seal_contract()
    rune_color_contract()
    rune_sequence_contract()
    late_depth_puzzle_contract()
    opening_shop_is_not_a_puzzle()
    deep_phase_contract()
    door_switch_art_contract()
    for stage in range(3, 10):
        sun_lattice_contract(stage)
    # Last: this archetype-harness entry already reaches kind 0 on main
    # (f022ab00), before any Sun Lattice change.
    wide_waystone_circuit_contract()
    print("[puzzles] PASS populated Trial/Waystone + distinct note colours + safe/audio-complete ordered "
          "runes + service exclusion + populated remote Aether Lattice/gate "
          "circuit + persistent gate crossing + Sun Lattice Stages 3-9")


if __name__ == "__main__":
    main()
