#!/usr/bin/env python3
"""v3.01 FF70 isolation WITH FF99 protocol fix.

The original build_v301_ff70_isolation.py was BROKEN because the colorize
handler did not set FF99=0x0D — so any ISR firing during the handler
would restore the wrong ROM bank on exit, garbling the game.

This rebuilds with FF99=0x0D protocol applied, then re-tests whether
FF70=2; FF70=1 alone breaks gameplay.

If gameplay WORKS: FF70 itself is fine. The bug is in attr_comp body.
If gameplay BREAKS: FF70 op itself is the disruptor — explains why
  attr_comp + GDMA + any bank-2 mechanism all broke.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import (load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader, create_tile_to_palette_subroutine)
from create_vblank_colorizer_v288 import create_conditional_palette_cached
from build_v296_phantomsafe import create_bg_sweep_viewport_gated
from build_v301_gdma import (BG_TABLE_BYTES, WRAM_BG_TABLE,
    create_inline_tile_copy_tileonly)


def build():
    rom = bytearray(Path("rom/Penta Dragon (J).gb").read_bytes())
    palettes = load_palettes_from_yaml(Path("palettes/penta_palettes_v097.yaml"))
    bg_data = bytearray(palettes['bg_data']); bg_data[56:64] = bg_data[0:8]
    palettes = {**palettes, 'bg_data': bytes(bg_data)}
    rom[0x143] = 0x80

    bank13 = 13 * 0x4000
    A = {'pal':0x6800,'bp':0x6880,'bs':0x68C0,'swj':0x68D0,'sdj':0x68D8,
         'sp':0x68E0,'shp':0x68E8,'tp':0x68F0,'pl':0x6900,'shm':0x69D0,
         'co':0x6A10,'tps':0x6B00,'cp':0x6C90,'sw':0x6CD0,
         'cz':0x6E00,'bt':0x7000}
    def w(a,d): rom[bank13+(a-0x4000):bank13+(a-0x4000)+len(d)] = d
    w(A['pal'], palettes['bg_data']); w(A['pal']+64, palettes['obj_data'])
    w(A['bp'], palettes['boss_palette_table']); w(A['bs'], palettes['boss_slot_table'])
    w(A['swj'], palettes['sara_witch_jet']); w(A['sdj'], palettes['sara_dragon_jet'])
    w(A['sp'], palettes['spiral_proj']); w(A['shp'], palettes['shield_proj'])
    w(A['tp'], palettes['turbo_proj'])
    w(A['pl'], create_palette_loader(A['pal'], A['bp'], A['bs'], A['swj'], A['sdj'], A['sp'], A['shp'], A['tp']))
    w(A['shm'], create_shadow_colorizer_main(A['co'], A['bs']))
    colz = bytearray(create_tile_based_colorizer(A['co'])); colz[1] = 0x0A
    w(A['co'], bytes(colz))
    w(A['tps'], create_tile_to_palette_subroutine())
    w(A['bt'], BG_TABLE_BYTES)
    w(A['cp'], create_conditional_palette_cached(A['pl']))
    sweep = bytearray(create_bg_sweep_viewport_gated(A['bt'], A['sw']))
    sweep[0:4] = bytes(4)
    w(A['sw'], bytes(sweep))

    # COLORIZE HANDLER with FF99 protocol fix AND FF70 isolation test
    code = bytearray()
    # FF99 protocol fix: save FF99, set to 0x0D, restore at exit
    code.extend([0xF0, 0x99, 0xF5, 0x3E, 0x0D, 0xE0, 0x99])
    code.extend([0xF0, 0x4F, 0xF5, 0xAF, 0xE0, 0x4F])

    # Cold-boot BG table copy
    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02 = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF])
    code.extend([0xAF, 0xEA, 0x00, 0xDF, 0xAF, 0xEA, 0x03, 0xDF])
    code.extend([0x21, A['bt'] & 0xFF, (A['bt'] >> 8) & 0xFF])
    code.extend([0x11, WRAM_BG_TABLE & 0xFF, (WRAM_BG_TABLE >> 8) & 0xFF])
    code.extend([0x06, 0x00])
    bg = len(code)
    code.extend([0x2A, 0x12, 0x13, 0x05])
    code.extend([0x20, (bg - (len(code) + 2)) & 0xFF])
    code[df02] = (len(code) - df02 - 1) & 0xFF

    code.extend([0xCD, A['cp'] & 0xFF, (A['cp'] >> 8) & 0xFF])
    code.extend([0xCD, A['sw'] & 0xFF, (A['sw'] >> 8) & 0xFF])

    # FFC1 gate: minimal payload + FF70 toggle test
    code.extend([0xF0, 0xC1, 0xB7])
    fg = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0xCD, 0x80, 0xFF])
    code.extend([0xCD, A['shm'] & 0xFF, (A['shm'] >> 8) & 0xFF])
    # FF70 isolation: DI; FF70=2; FF70=1; EI
    code.extend([0xF3])
    code.extend([0x3E, 0x02, 0xE0, 0x70])
    code.extend([0x3E, 0x01, 0xE0, 0x70])
    code.extend([0xFB])
    code[fg] = (len(code) - fg - 1) & 0xFF

    code.extend([0xF1, 0xE0, 0x4F, 0xF1, 0xE0, 0x99, 0xC9])
    w(A['cz'], bytes(code))
    print(f"  colorize handler (FF99 fix + FF70 isolation): {len(code)} bytes")

    hook = bytes([0xF0, 0x99, 0xF5, 0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F,
                  0xCB, 0x37, 0x47, 0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00,
                  0x2F, 0xE6, 0x0F, 0xB0, 0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
                  0x3E, 0x0D, 0xEA, 0x00, 0x20, 0xCD, A['cz'] & 0xFF, (A['cz'] >> 8) & 0xFF,
                  0xF1, 0xEA, 0x00, 0x20, 0xC9])
    rom[0x0824:0x0824 + 47] = hook + bytes(47 - len(hook))
    rom[0x06D5:0x06D8] = bytes(3)
    rom[0x003B] = 0xC9

    inline_code = create_inline_tile_copy_tileonly()
    rom[0x42A7:0x42A7 + len(inline_code)] = inline_code
    rom[0x42A7 + len(inline_code):0x436E] = bytes(0x436D - 0x42A7 + 1 - len(inline_code))

    chk = 0
    for b in rom[0x134:0x14D]: chk = (chk - b - 1) & 0xFF
    rom[0x14D] = chk

    out = Path("rom/working/penta_dragon_dx_v301_ff70_with_ff99fix.gb")
    out.write_bytes(rom)
    print(f"Wrote {out}")


if __name__ == "__main__":
    build()
