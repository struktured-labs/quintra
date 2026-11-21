#!/usr/bin/env python3
"""Live-ROM contract for the Zelda-style B-item icon picker.

Start a run, open Pack -> SELECT, and check the framed icon wells, the gold
cursor, label-correct names/tips, bidirectional owned-item walking, aim-mode
toggle, and the 1-row equipped-B HUD box. Inventory is poked; this is not a
merchant run. See docs/superpowers/specs/2026-11-15-b-item-icon-picker.md.
"""
import os
import re
import sys
from pathlib import Path

from pyboy import PyBoy
from PIL import Image
from quintra_vignettes import mute_vignettes
from quintra_class_select import downs_to_class

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
OUT = Path(os.environ.get("QUINTRA_BMENU_OUT", str(ROOT / "tmp" / "b-item-picker")))
OUT.mkdir(parents=True, exist_ok=True)

ITEM_BOOMERANG = 45
ITEM_HOOKSHOT = 46
ITEM_MORNINGSTAR = 47
ITEM_BOMBS = 48
CLASS_POWER = 10  # Wolfkin Moonfire

INV_FRAME_H = 0xF6
INV_FRAME_VL = 0xF7
INV_FRAME_VR = 0xF8
INV_FRAME_TL = 0xF9
INV_FRAME_TR = 0xFA
INV_FRAME_BL = 0xFB
INV_FRAME_BR = 0xFC
HUD_B_LETTER = 0xF0
HUD_B_ICON = 0xF1
SCREEN_TITLE = 1
SCREEN_CLASS_SELECT = 2
SCREEN_INTRO = 4
SCREEN_ROOM = 5
SCREEN_INVENTORY = 9
PROJ_AUX_HOOKSHOT = 0xF5
WELL_COLS = (2, 5, 8, 11, 14)


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


SCREEN = addr("_loop_current_screen")
PLAYER = addr("_player")
ENTITIES = addr("_entities")
ACTIVE = PLAYER + 18
INV0 = PLAYER + 24
AIM_MODE = addr("_player_penta_aim")


def press(pb, button, held=5, released=8):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot_wolfkin_pack():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    # Power-on intro: START skips it. Title uses START, then downs to Wolfkin.
    if pb.memory[SCREEN] == SCREEN_INTRO:
        press(pb, "start")
        pb.tick(30)
    if pb.memory[SCREEN] == SCREEN_TITLE:
        press(pb, "start")
        pb.tick(30)
    assert pb.memory[SCREEN] == SCREEN_CLASS_SELECT, (
        f"expected class select, got {pb.memory[SCREEN]}")
    for _ in range(downs_to_class(0)):
        press(pb, "down")
    press(pb, "a")
    for _ in range(90):
        if pb.memory[SCREEN] in (SCREEN_ROOM, 3, 6):  # run_init or vignette
            mute_vignettes(pb, ROM)
            break
        pb.tick()
    mute_vignettes(pb, ROM)
    for _ in range(120):
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
        if pb.memory[SCREEN] == 6:  # vignette: skip
            press(pb, "start")
        pb.tick()
    assert pb.memory[SCREEN] == SCREEN_ROOM, f"did not reach room ({pb.memory[SCREEN]})"
    pb.tick(60)
    press(pb, "start", held=8, released=16)
    pb.tick(16)
    assert pb.memory[SCREEN] == SCREEN_INVENTORY, f"did not open PACK ({pb.memory[SCREEN]})"
    return pb


def open_aim(pb):
    press(pb, "select")
    for _ in range(16):
        pb.tick()
    assert pb.memory[SCREEN] == SCREEN_INVENTORY, "left PACK on SELECT"


def map_base(pb):
    return 0x9C00 if pb.memory[0xFF40] & 0x08 else 0x9800


def row_tiles(pb, y, x=0, w=20):
    base = map_base(pb) + y * 32 + x
    return list(pb.memory[base:base + w])


def tile_char(tile):
    # font_min after font_init: 0=space, 1..10='0'..'9', 11..36='A'..'Z'.
    if tile == 0:
        return " "
    if 1 <= tile <= 10:
        return chr(ord("0") + tile - 1)
    if 11 <= tile <= 36:
        return chr(ord("A") + tile - 11)
    return "?"


def decode_row(pb, y, x=1, w=18):
    return "".join(tile_char(t) for t in row_tiles(pb, y, x, w)).rstrip()


def well_corners(pb, slot):
    col = WELL_COLS[slot]
    m = map_base(pb)
    tl = pb.memory[m + 4 * 32 + col]
    tr = pb.memory[m + 4 * 32 + col + 2]
    bl = pb.memory[m + 6 * 32 + col]
    br = pb.memory[m + 6 * 32 + col + 2]
    return tl, tr, bl, br


def well_attr(pb, slot):
    col = WELL_COLS[slot]
    vbk = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 1
    pal = pb.memory[map_base(pb) + 4 * 32 + col] & 7
    pb.memory[0xFF4F] = vbk
    return pal


def icon_tile(pb, slot):
    return pb.memory[0xFE00 + slot * 4 + 2]


def icon_visible(pb, slot):
    y = pb.memory[0xFE00 + slot * 4]
    x = pb.memory[0xFE00 + slot * 4 + 1]
    return y != 0 and x != 0


def grant(pb, *ids):
    # Wipe tool slots then write the requested tools into inventory[0..].
    for i in range(16):
        cur = pb.memory[INV0 + i]
        if cur in (ITEM_BOOMERANG, ITEM_HOOKSHOT, ITEM_MORNINGSTAR, ITEM_BOMBS, 0xFF):
            pb.memory[INV0 + i] = 0xFF
    for n, item in enumerate(ids):
        pb.memory[INV0 + n] = item


def shot_live(pb, marker):
    for i in range(32):
        e = ENTITIES + i * 28
        if pb.memory[e] == 1 and pb.memory[e + 1] & 1 and pb.memory[e + 23] == marker:
            return True
    return False


def save_shot(pb, name, scale=4):
    img = pb.screen.image.convert("RGB")
    img.save(OUT / f"{name}.png")
    big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    big.save(OUT / f"{name}@4x.png")
    return img


def main():
    pb = boot_wolfkin_pack()
    try:
        open_aim(pb)
        assert decode_row(pb, 0, 5, 9).strip() == "B ITEMS", decode_row(pb, 0, 5, 9)
        assert "PICK YOUR B ITEM" in decode_row(pb, 2, 1, 18), decode_row(pb, 2, 1, 18)
        for slot in range(5):
            tl, tr, bl, br = well_corners(pb, slot)
            assert (tl, tr, bl, br) == (INV_FRAME_TL, INV_FRAME_TR, INV_FRAME_BL, INV_FRAME_BR), (
                f"well {slot} frames", tl, tr, bl, br)
        # Gold cursor on the class power; unowned tools are dim empty frames.
        assert well_attr(pb, 0) == 1, f"class well pal {well_attr(pb, 0)}"
        for slot in range(1, 5):
            assert well_attr(pb, slot) == 0, f"unowned well {slot} pal {well_attr(pb, slot)}"
            assert not icon_visible(pb, slot), f"unowned well {slot} showed an icon"
        assert icon_visible(pb, 0), "class power icon missing"
        assert "MOONFIRE" in decode_row(pb, 8, 1, 18), decode_row(pb, 8, 1, 18)
        assert "FLAME WARD" in decode_row(pb, 9, 1, 18), decode_row(pb, 9, 1, 18)
        assert pb.memory[ACTIVE] == CLASS_POWER
        save_shot(pb, "picker-howl")

        # Grant Hookshot only. Right skips the empty Boomerang well.
        grant(pb, ITEM_HOOKSHOT)
        press(pb, "right")
        for _ in range(8):
            pb.tick()
        assert pb.memory[ACTIVE] == ITEM_HOOKSHOT, pb.memory[ACTIVE]
        assert well_attr(pb, 2) == 1, f"hook well pal {well_attr(pb, 2)}"
        assert well_attr(pb, 0) == 2, f"owned class well pal {well_attr(pb, 0)}"
        assert well_attr(pb, 1) == 0, "empty boomerang was selectable"
        assert "HOOKSHOT" in decode_row(pb, 8, 1, 18), decode_row(pb, 8, 1, 18)
        assert "LATCH AND PULL" in decode_row(pb, 9, 1, 18), decode_row(pb, 9, 1, 18)
        assert icon_visible(pb, 2)
        save_shot(pb, "picker-hookshot")
        press(pb, "right")
        for _ in range(8):
            pb.tick()
        assert pb.memory[ACTIVE] == CLASS_POWER, "right did not wrap to class power"
        assert well_attr(pb, 0) == 1

        # All four tools: Left/Right and Up/Down walk both ways and wrap.
        grant(pb, ITEM_BOOMERANG, ITEM_HOOKSHOT, ITEM_MORNINGSTAR, ITEM_BOMBS)
        # Re-enter so wells refresh ownership before walking.
        press(pb, "b")
        pb.tick(20)
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.tick(40)
        press(pb, "start", held=8, released=16)
        pb.tick(16)
        assert pb.memory[SCREEN] == SCREEN_INVENTORY, (
            f"reopen PACK failed ({pb.memory[SCREEN]})")
        open_aim(pb)
        order = []
        for _ in range(5):
            order.append(pb.memory[ACTIVE])
            press(pb, "right")
            for _ in range(6):
                pb.tick()
        assert order == [CLASS_POWER, ITEM_BOOMERANG, ITEM_HOOKSHOT,
                         ITEM_MORNINGSTAR, ITEM_BOMBS], order
        assert pb.memory[ACTIVE] == CLASS_POWER
        back = []
        for _ in range(5):
            press(pb, "left")
            for _ in range(6):
                pb.tick()
            back.append(pb.memory[ACTIVE])
        assert back == [ITEM_BOMBS, ITEM_MORNINGSTAR, ITEM_HOOKSHOT,
                        ITEM_BOOMERANG, CLASS_POWER], back
        for key, expect in (("down", ITEM_BOOMERANG), ("up", CLASS_POWER)):
            press(pb, key)
            for _ in range(6):
                pb.tick()
            assert pb.memory[ACTIVE] == expect, (key, pb.memory[ACTIVE])
        save_shot(pb, "picker-all-owned")

        # A flips aim mode and does not change the equipped item.
        before = pb.memory[ACTIVE]
        mode = pb.memory[AIM_MODE]
        press(pb, "a")
        for _ in range(8):
            pb.tick()
        assert pb.memory[AIM_MODE] == (mode ^ 1), "A did not toggle HOLD AIM"
        assert pb.memory[ACTIVE] == before
        label = decode_row(pb, 12, 1, 18)
        assert "HOLD AIM" in label or "CLASSIC" in label, label
        press(pb, "a")
        for _ in range(8):
            pb.tick()
        assert pb.memory[AIM_MODE] == mode

        # SELECT reaches Gear; B resumes the room.
        press(pb, "select")
        for _ in range(16):
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_INVENTORY
        gear = decode_row(pb, 0, 4, 12)
        assert "WAYGEAR" in gear or "GEAR" in gear, gear
        press(pb, "b")
        pb.tick(30)
        assert pb.memory[SCREEN] == SCREEN_ROOM, f"B did not resume the room ({pb.memory[SCREEN]})"

        # Equipped-B HUD box (1-row): letter + icon in cols 10-11.
        # Equip hookshot, return to play, wait a beat so notices (if any) lapse.
        press(pb, "start")
        for _ in range(16):
            pb.tick()
        open_aim(pb)
        # Walk to hookshot (all tools still owned; from class power, two Rights).
        while pb.memory[ACTIVE] != ITEM_HOOKSHOT:
            press(pb, "right")
            for _ in range(6):
                pb.tick()
        press(pb, "b")
        for _ in range(50):
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_ROOM
        win = list(pb.memory[0x9C00 + 10:0x9C00 + 12])
        assert win == [HUD_B_LETTER, HUD_B_ICON], f"HUD B box {win}"
        save_shot(pb, "hud-hookshot")

        # B fires a hookshot projectile.
        pb.button_press("b")
        pb.tick(3)
        pb.button_release("b")
        found = False
        for _ in range(24):
            if shot_live(pb, PROJ_AUX_HOOKSHOT):
                found = True
                break
            pb.tick()
        assert found, "equipped Hookshot did not fire on B"
        save_shot(pb, "hookshot-fire")

        # Animate a short picker walk for the GIF.
        press(pb, "start")
        for _ in range(16):
            pb.tick()
        open_aim(pb)
        frames = [save_shot(pb, "gif-00")]
        for i in range(1, 6):
            press(pb, "right")
            for _ in range(10):
                pb.tick()
            frames.append(save_shot(pb, f"gif-{i:02d}"))
        scaled = [f.resize((f.width * 4, f.height * 4), Image.NEAREST) for f in frames]
        scaled[0].save(OUT / "picker-walk@4x.gif", save_all=True, append_images=scaled[1:],
                       duration=280, loop=0)
    finally:
        pb.stop(save=False)
    print(f"[b-item-picker] PASS  shots in {OUT}")


if __name__ == "__main__":
    sys.exit(main())
