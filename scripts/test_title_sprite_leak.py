#!/usr/bin/env python3
"""Title OAM must not keep the fight that just killed the player.

GAME OVER hides sprites by clearing the LCDC bit and leaves shadow OAM
alone. The title then enables sprites for its five champions (objects
0..19). Anything still sitting in slots 20..39 is drawn on top of the menu.

On the Crystal Colossus that is both halves of the owner's capture: the
body's bottom row (tiles 52..55) sits on PRESS START, and the boss pellets
that were drawn first (tile 208, plus an impact spark at tile 33) remain
as the stray dots around the logo. A death that only produced one of those
does not prove the title clears the other.
"""
import shutil
import tempfile
from pathlib import Path

from pyboy import PyBoy
from test_boss_identity import EN, PL, ROM, addr, enter_boss

SCREEN = addr("_loop_current_screen")

ROOT = Path(__file__).resolve().parent.parent
OAM = 0xFE00
CLASS_BASE = 0
WALK_BASE = 82
STRIDE = 4
SETTLE = 16
OUT = ROOT / "tmp" / "title-sprite-leak"
# SPR_BOSS_BIG is the 4x4 Colossus, sixteen tiles.
BODY_LO = 40
BODY_HI = 55
# Boss rooms replace the resident atlas at 208..223 with shot art
# (pellet, orb, seed, bolt, crescent, and the split frames). Ordinary
# bullets are 28/29; the impact spark is 33.
BOSS_SHOT_TILES = set(range(208, 224))
BULLET_TILES = {28, 29, 33}
PROJECTILE_TILES = BOSS_SHOT_TILES | BULLET_TILES


def font_tiles(text):
    return bytes(0 if char == " " else ord(char) - ord("A") + 11 for char in text)


def press(pb, button, held=12, released=6):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def wait_screen(pb, screen, limit, label):
    for _ in range(limit):
        pb.tick()
        if pb.memory[SCREEN] == screen:
            return
    raise AssertionError(
        f"{label} never reached screen {screen}; now {pb.memory[SCREEN]}"
    )


def settle_title(pb):
    """Advance a fixed number of frames after the title screen is current.

    Boot and the game-over transition both run title_enter and one
    title_draw inside the frame that first publishes SCREEN_TITLE. The
    same extra frame count then lands on the same palette pulse and
    champion pose, so the framebuffer itself is comparable.
    """
    for _ in range(SETTLE):
        pb.tick()


def oam_bytes(pb, index):
    base = OAM + index * 4
    return tuple(pb.memory[base:base + 4])


def live_tail(pb):
    rows = []
    for index in range(20, 40):
        y, x, tile, prop = oam_bytes(pb, index)
        if y or x:
            rows.append((index, y, x, tile, prop))
    return rows


def sprite_kind(tile):
    if BODY_LO <= tile <= BODY_HI:
        return "boss body"
    if tile in PROJECTILE_TILES:
        return "projectile"
    return "other"


def describe_tail(rows):
    return ", ".join(
        f"{index}@y={y} x={x} tile={tile} ({sprite_kind(tile)})"
        for index, y, x, tile, _prop in rows
    )


def assert_title_sprites(pb, label):
    assert pb.memory[SCREEN] == 1, f"{label} left screen {pb.memory[SCREEN]}"
    assert pb.memory[0xFF40] & 0x02, f"{label} left sprites disabled"
    leftovers = []
    for sprite in range(40):
        y, x, tile, _prop = oam_bytes(pb, sprite)
        if not (y or x):
            continue
        kind = sprite_kind(tile)
        if kind != "other" or sprite >= 20:
            leftovers.append(
                f"{sprite}@y={y} x={x} tile={tile} ({kind})"
            )
    assert not leftovers, (
        f"{label} left the fight on the title: " + ", ".join(leftovers)
    )
    for sprite in range(20):
        y, x, tile, _prop = oam_bytes(pb, sprite)
        champion, part = divmod(sprite, 4)
        expected = (
            CLASS_BASE + champion * STRIDE + part,
            WALK_BASE + champion * STRIDE + part,
        )
        assert tile in expected and 16 <= y < 144 and 8 <= x < 168, (
            f"{label} title spirit {sprite} drifted: "
            f"y={y} x={x} tile={tile} expected {expected}"
        )


def frame_bytes(pb):
    # Copy immediately. The ndarray aliases the emulator's framebuffer.
    return pb.screen.ndarray.tobytes()


def save_frame(pb, name):
    try:
        from PIL import Image
    except ImportError:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    image = pb.screen.ndarray
    Image.fromarray(image[:, :, :3]).save(OUT / name)


def bg_row(pb, row, col, length):
    return bytes(pb.memory[0x9800 + row * 32 + col:0x9800 + row * 32 + col + length])


def sram_open(pb):
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = 0


def sram_close(pb):
    pb.memory[0x0000] = 0


def assert_suspend_cleared(pb, label):
    sram_open(pb)
    magic = bytes(pb.memory[0xA000:0xA002])
    sram_close(pb)
    assert magic != b"QS", f"{label} left the suspend save runnable: {magic!r}"


def kill_to_title(pb, label, need_body=False, projectile_tiles=None):
    pb.memory[PL + 2] = 0
    wait_screen(pb, 11, 240, f"{label} game over")
    # Give the banked game-over enter a frame to finish its LCDC write
    # before sampling the OAM the fight left behind. Slots 0..19 are
    # rewritten by the champions, so only 20..39 can still be on screen.
    pb.tick()
    assert pb.memory[0xFF40] & 0x02 == 0, f"{label} game over still showed sprites"
    tail = live_tail(pb)
    assert tail, (
        f"{label} never parked a sprite in OAM 20..39, so this death "
        "cannot prove the title clears the tail"
    )
    if need_body:
        body = [row for row in tail if BODY_LO <= row[3] <= BODY_HI]
        assert body, (
            f"{label} game over left no Colossus body in OAM 20..39 "
            f"({describe_tail(tail)}). That row is the striped remnant "
            "on PRESS START; a shot-only tail does not cover it."
        )
    if projectile_tiles is not None:
        shots = [row for row in tail if row[3] in projectile_tiles]
        assert shots, (
            f"{label} game over left no projectile in OAM 20..39 "
            f"({describe_tail(tail)}). Those are the stray dots around "
            "the title; a body-only tail does not cover them."
        )
    press(pb, "start")
    wait_screen(pb, 1, 60, f"{label} title")
    settle_title(pb)
    assert_title_sprites(pb, label)
    prompt = bg_row(pb, 12, 4, 12)
    assert prompt == font_tiles("PRESS  START"), (
        f"{label} title still offered continue or dropped the start prompt: "
        f"{list(prompt)}"
    )
    assert_suspend_cleared(pb, label)
    return frame_bytes(pb)


def spawn_hostile_shots(pb, count):
    """Fill the entity table with stationary enemy shots.

    A quiet foyer only uses the first handful of OAM entries, which the
    title spirits overwrite. A full volley is what pushes bullets into
    the slots the old title left untouched.
    """
    pb.memory[PL + 15] = 255
    # Stack the volley on the hero. That cell is in-bounds, so the shots
    # survive the hostile despawn check and still consume distinct objects.
    # The foyer already has residents in the low slots; these shots push
    # the hardware cursor into 20..39, which the old title left untouched.
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    made = 0
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep + 1] & 1:
            continue
        for byte in range(28):
            pb.memory[ep + byte] = 0
        pb.memory[ep] = 1
        pb.memory[ep + 1] = 0x03
        put_fix8(pb, ep + 2, px)
        put_fix8(pb, ep + 6, py)
        pb.memory[ep + 12] = 28  # SPR_BULLET
        pb.memory[ep + 13] = 4
        pb.memory[ep + 14] = 1
        pb.memory[ep + 16] = 255
        pb.memory[ep + 25] = 0x44
        pb.memory[ep + 26] = 1
        made += 1
        if made >= count:
            break
    assert made >= count, f"only spawned {made} hostile shots"
    for _ in range(4):
        pb.tick()


def wait_room_ready(pb, label):
    # SCREEN_ROOM is published before room_enter finishes its banked
    # upload. Wait until the hero sprite is actually on the glass.
    wait_screen(pb, 5, 180, label)
    for _ in range(120):
        pb.tick()
        y, x, _tile, _prop = oam_bytes(pb, 0)
        if (pb.memory[0xFF40] & 0x02) and y and x and pb.memory[PL + 2]:
            return
    raise AssertionError(f"{label} never presented the player sprite")


def boot_room(pb):
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    wait_room_ready(pb, "fresh room")


def fresh_title_frame():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    wait_screen(pb, 1, 300, "fresh title")
    settle_title(pb)
    assert_title_sprites(pb, "fresh boot")
    image = frame_bytes(pb)
    save_frame(pb, "fresh-title.png")
    pb.stop(save=False)
    return image


def assert_same_frame(actual, expected, label):
    # The five champions bob one pixel on an 8-frame grid. Boot and a
    # game-over return do not land on the same phase, so the sprite band
    # is allowed to differ; OAM asserts that band. Everything under it is
    # the logo, lore, and prompt, which is where a clipped Colossus shows.
    assert len(actual) == 144 * 160 * 4 and len(expected) == len(actual), (
        f"{label} framebuffer size drifted: {len(actual)} vs {len(expected)}"
    )
    row = 160 * 4
    top = 40 * row
    actual_body = actual[top:]
    expected_body = expected[top:]
    if actual_body == expected_body:
        return
    differ = sum(a != b for a, b in zip(actual_body, expected_body))
    raise AssertionError(
        f"{label} title framebuffer diverged below the champions "
        f"({differ} bytes)"
    )


def boss_death(reference):
    pb, _boss = enter_boss(0, keep_open=True)
    # The owner's title capture is this exact pair: body tiles on the
    # prompt, and boss pellets (tile 208) still queued behind them.
    image = kill_to_title(
        pb, "crystal boss", need_body=True, projectile_tiles=BOSS_SHOT_TILES
    )
    save_frame(pb, "crystal-title-after.png")
    assert_same_frame(image, reference, "crystal boss")
    # Class select shows sprites too, and it only rewrites objects 0..4.
    # The tail has to already be gone before that screen enables them.
    press(pb, "start")
    wait_screen(pb, 2, 60, "class select")
    for _ in range(8):
        pb.tick()
    leaked = [
        i for i in range(5, 40)
        if oam_bytes(pb, i)[0] or oam_bytes(pb, i)[1]
    ]
    assert not leaked, f"class select inherited title/fight sprites: {leaked}"
    pb.stop(save=False)


def crowded_enemy_death(reference):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    boot_room(pb)
    spawn_hostile_shots(pb, 16)
    assert any(row[3] == 28 for row in live_tail(pb)), (
        "enemy volley never reached OAM 20..39"
    )
    image = kill_to_title(pb, "enemy volley", projectile_tiles=BULLET_TILES)
    save_frame(pb, "enemy-title-after.png")
    assert_same_frame(image, reference, "enemy volley")
    pb.stop(save=False)


def continue_then_die(reference):
    """A suspended room must resume, and dying there must still clear OAM."""
    with tempfile.TemporaryDirectory(prefix="quintra-title-oam-") as td:
        cart = Path(td) / "quintra.gbc"
        battery = Path(td) / "quintra.sav"
        shutil.copy2(ROM, cart)
        first = PyBoy(str(cart), window="null", cgb=True)
        boot_room(first)
        sram_open(first)
        assert bytes(first.memory[0xA000:0xA002]) == b"QS", (
            "room entry did not write a suspend save to continue from"
        )
        sram_close(first)
        battery_io = battery.open("w+b")
        first.stop(save=True, ram_file=battery_io)
        battery_io.flush()
        battery_io.seek(0)

        second = PyBoy(str(cart), window="null", cgb=True, ram_file=battery_io)
        wait_screen(second, 1, 300, "continue title")
        settle_title(second)
        assert_title_sprites(second, "continue title")
        assert bg_row(second, 11, 4, 14) == font_tiles("A     CONTINUE"), (
            "suspended run did not offer continue"
        )
        press(second, "a")
        wait_room_ready(second, "continued room")
        spawn_hostile_shots(second, 16)
        assert any(row[3] == 28 for row in live_tail(second)), (
            "continued room volley never reached OAM 20..39"
        )
        image = kill_to_title(
            second, "continued run", projectile_tiles=BULLET_TILES
        )
        save_frame(second, "continue-title-after.png")
        assert_same_frame(image, reference, "continued run")
        # A on this title must not walk back into the dead run.
        press(second, "a")
        for _ in range(20):
            second.tick()
        assert second.memory[SCREEN] == 1, "cleared suspend still resumed on A"
        second.stop(save=False)
        battery_io.close()


def main():
    reference = fresh_title_frame()
    boss_death(reference)
    crowded_enemy_death(reference)
    continue_then_die(reference)
    print(
        "[title-sprite-leak] PASS crystal boss (body and pellets), "
        "enemy volley, and continue-then-death leave only the five "
        "title spirits"
    )


if __name__ == "__main__":
    main()
