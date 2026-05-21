#!/usr/bin/env python3
"""Variant: General-mode GDMA (HDMA5=0x3F) — atomic copy while VBK=1.

The HBlank-mode HDMA (HDMA5=0xBF) lets HDMA continue running after
the colorize handler restores VBK=0. Subsequent HBlanks then write
to VRAM bank 0 (TILE INDICES) instead of bank 1 (attributes) →
visual corruption.

General-mode GDMA halts CPU until the entire 1024-byte transfer
completes (~512T at single-speed CGB). VBK stays at 1 throughout
since we don't return to game code until after the transfer.

Usage: python build_v301_attr_gdma_general.py <rows>
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
from build_v301_attr_param import create_attr_computation_n


def create_gdma_general() -> bytes:
    """Atomic GDMA general-mode: ~512T halt, VBK stays 1 throughout."""
    code = bytearray()
    code.extend([0xF3])                       # DI
    code.extend([0x3E, 0x01, 0xE0, 0x4F])     # VBK = 1 (attribute layer)
    code.extend([0x3E, 0x02, 0xE0, 0x70])     # FF70 = 2 (WRAM bank 2)

    code.extend([0x3E, 0xD0, 0xE0, 0x51])     # HDMA1 = 0xD0 (src high)
    code.extend([0xAF, 0xE0, 0x52])           # HDMA2 = 0x00 (src low)

    code.extend([0xF0, 0x40])                 # LDH A,[LCDC]
    code.extend([0xE6, 0x08])                 # AND 0x08
    code.extend([0x28, 0x04])                 # JR Z, +4
    code.extend([0x3E, 0x9C])                 # LD A, 0x9C
    code.extend([0x18, 0x02])                 # JR +2
    code.extend([0x3E, 0x98])                 # LD A, 0x98
    code.extend([0xE0, 0x53])                 # HDMA3 = 0x98 or 0x9C
    code.extend([0xAF, 0xE0, 0x54])           # HDMA4 = 0x00

    code.extend([0x3E, 0x3F, 0xE0, 0x55])     # HDMA5 = 0x3F → general mode start, halts CPU

    # After GDMA: CPU resumed, VBK still 1, FF70 still 2
    code.extend([0x3E, 0x01, 0xE0, 0x70])     # FF70 = 1
    code.extend([0xAF, 0xE0, 0x4F])           # VBK = 0
    code.extend([0xFB])                       # EI
    code.extend([0xC9])                       # RET
    return bytes(code)


def build(n_rows: int):
    rom = bytearray(Path("rom/Penta Dragon (J).gb").read_bytes())
    palettes = load_palettes_from_yaml(Path("palettes/penta_palettes_v097.yaml"))
    bg_data = bytearray(palettes['bg_data']); bg_data[56:64] = bg_data[0:8]
    palettes = {**palettes, 'bg_data': bytes(bg_data)}
    rom[0x143] = 0x80

    bank13 = 13 * 0x4000
    A = {'pal':0x6800,'bp':0x6880,'bs':0x68C0,'swj':0x68D0,'sdj':0x68D8,
         'sp':0x68E0,'shp':0x68E8,'tp':0x68F0,'pl':0x6900,'shm':0x69D0,
         'co':0x6A10,'tps':0x6B00,'cp':0x6C90,'sw':0x6CD0,'gd':0x6D80,
         'cz':0x6E00,'bt':0x7000,'ac':0x7100}
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
    sw = bytearray(create_bg_sweep_viewport_gated(A['bt'], A['sw'])); sw[0:4] = bytes(4)
    w(A['sw'], bytes(sw))
    w(A['ac'], create_attr_computation_n(A['bt'], n_rows))
    w(A['gd'], create_gdma_general())

    code = bytearray()
    code.extend([0xF0, 0x99, 0xF5, 0x3E, 0x0D, 0xE0, 0x99])
    code.extend([0xF0, 0x4F, 0xF5, 0xAF, 0xE0, 0x4F])
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
    code.extend([0xF0, 0xC1, 0xB7])
    fg = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0xCD, 0x80, 0xFF])
    code.extend([0xCD, A['shm'] & 0xFF, (A['shm'] >> 8) & 0xFF])
    code.extend([0xCD, A['ac'] & 0xFF, (A['ac'] >> 8) & 0xFF])
    code.extend([0xCD, A['gd'] & 0xFF, (A['gd'] >> 8) & 0xFF])
    code[fg] = (len(code) - fg - 1) & 0xFF
    code.extend([0xF1, 0xE0, 0x4F, 0xF1, 0xE0, 0x99, 0xC9])
    w(A['cz'], bytes(code))

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
    out = Path(f"rom/working/penta_dragon_dx_v301_gen_R{n_rows}.gb")
    out.write_bytes(rom)
    print(f"Wrote {out}")


if __name__ == "__main__":
    n = int(sys.argv[1])
    build(n)
