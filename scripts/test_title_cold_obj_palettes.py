#!/usr/bin/env python3
"""Title champions must get their class colors even if LCD-off OBJ writes fail.

On a MiSTer / real CGB, palette RAM can power on zeroed, and some cores drop
CGB palette writes made while the LCD is off. The title used to load OBJ
palettes 1..5 only before DISPLAY_ON, so Sauran (OBJ 2) and Corvin (OBJ 3)
could stay black on first boot. This test wipes every OBJ slot whenever the
LCD is off, then asserts that after the title's LCD-on VBlank reload the
five champions have their authored palettes and colors.
"""
import io
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"


def bgr555(r, g, b):
    return (b << 10) | (g << 5) | r


# class_obj_palettes[] in src/render/class_palettes.c, indexed by spirit
# and loaded into OBJ slots 1..5 on the title.
CLASS_OBJ = (
    (bgr555(0, 0, 0), bgr555(28, 22, 14), bgr555(14, 8, 4), bgr555(30, 28, 20)),  # Wolfkin
    (bgr555(0, 0, 0), bgr555(10, 24, 8), bgr555(4, 12, 4), bgr555(24, 30, 12)),   # Sauran
    (bgr555(0, 0, 0), bgr555(14, 10, 22), bgr555(6, 4, 12), bgr555(26, 24, 30)),  # Corvin
    (bgr555(0, 0, 0), bgr555(10, 20, 28), bgr555(4, 8, 18), bgr555(20, 30, 30)),  # Picsean
    (bgr555(0, 0, 0), bgr555(30, 26, 6), bgr555(12, 10, 2), bgr555(30, 14, 4)),   # Vespine
)
NAMES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")
# Visible 16x16 boxes: OAM X = 24,52,80,108,136 → screen x = X-8.
SPIRIT_X = (16, 44, 72, 100, 128)
SPIRIT_Y = 15


def zero_obj_palettes(pb):
    for slot in range(8):
        pb.memory[0xFF6A] = 0x80 | (slot << 3)
        for _ in range(8):
            pb.memory[0xFF6B] = 0


def read_obj_palettes(pb):
    data = []
    for index in range(64):
        pb.memory[0xFF6A] = index
        data.append(pb.memory[0xFF6B])
    slots = []
    for slot in range(8):
        colors = []
        for i in range(4):
            lo = data[slot * 8 + i * 2]
            hi = data[slot * 8 + i * 2 + 1]
            colors.append((lo | (hi << 8)) & 0x7FFF)
        slots.append(tuple(colors))
    return slots


def lcd_on(pb):
    return bool(pb.memory[0xFF40] & 0x80)


def boot_wiping_lcd_off_obj(rom):
    """Zero OBJ palette RAM before every frame while the LCD is off."""
    pb = PyBoy(str(rom), window="null", cgb=True, ram_file=io.BytesIO(bytes(32 * 1024)))
    for frame in range(240):
        if not lcd_on(pb):
            zero_obj_palettes(pb)
        pb.tick()
        if lcd_on(pb) and pb.memory[0xFE00] != 0:
            # Title spirits have been placed; give the LCD-on VBlank
            # reload and one title_draw a couple of frames to run.
            for _ in range(8):
                if not lcd_on(pb):
                    zero_obj_palettes(pb)
                pb.tick()
            return pb, frame
    pb.stop(save=False)
    raise AssertionError("title sprites never appeared within 240 frames")



def main():
    assert ROM.is_file(), f"missing test ROM {ROM}"
    pb, appear = boot_wiping_lcd_off_obj(ROM)
    try:
        obj = read_obj_palettes(pb)
        assert obj[0] == (0, 0, 0, 0), f"OBJ 0 should stay black, got {obj[0]}"
        assert obj[6] == (0, 0, 0, 0), f"OBJ 6 should stay black, got {obj[6]}"
        assert obj[7] == (0, 0, 0, 0), f"OBJ 7 should stay black, got {obj[7]}"
        for i, name in enumerate(NAMES):
            slot = i + 1
            got = obj[slot]
            exp = CLASS_OBJ[i]
            assert got == exp, (
                f"{name} OBJ {slot} after LCD-on reload was {tuple(hex(c) for c in got)}, "
                f"expected {tuple(hex(c) for c in exp)} (appeared at frame {appear})"
            )
            # OAM props must still name that slot.
            for part in range(4):
                sprite = i * 4 + part
                prop = pb.memory[0xFE00 + sprite * 4 + 3]
                assert (prop & 7) == slot, (
                    f"{name} sprite {sprite} uses OBJ {prop & 7}, expected {slot}"
                )

        frame = pb.screen.ndarray
        # Authored body colors. This PyBoy build expands 5-bit channels as
        # val << 3 (no low-bit fill).
        def ch(v):
            return v << 3

        expected_body = {
            "Wolfkin": (ch(28), ch(22), ch(14)),
            "Sauran": (ch(10), ch(24), ch(8)),
            "Corvin": (ch(14), ch(10), ch(22)),
            "Picsean": (ch(10), ch(20), ch(28)),
            "Vespine": (ch(30), ch(26), ch(6)),
        }
        title_bg = (8, 0, 40)
        for i, name in enumerate(NAMES):
            x, y = SPIRIT_X[i], SPIRIT_Y
            colors = set()
            for yy in range(y, y + 16):
                for xx in range(x, x + 16):
                    pix = frame[yy, xx]
                    colors.add((int(pix[0]), int(pix[1]), int(pix[2])))
            body = expected_body[name]
            assert body in colors, (
                f"{name} sprite is missing body color {body}; "
                f"got {sorted(colors)[:12]} — LCD-off wipe was not recovered"
            )
            if name in ("Sauran", "Corvin"):
                non_bg = {c for c in colors if c != title_bg and c != (0, 0, 0)}
                assert non_bg, f"{name} is a black silhouette after LCD-off palette wipe"
        print(
            f"PASS title cold OBJ palettes recovered after LCD-off wipe "
            f"(title visible around frame {appear})"
        )
    finally:
        pb.stop(save=False)


if __name__ == "__main__":
    main()
