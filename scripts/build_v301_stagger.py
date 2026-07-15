#!/usr/bin/env python3
"""v3.01 stagger: compute 8 rows/frame but alternate WHICH 8 rows.

Frame N (even):   rows 0-7   → HL = 0xC1A0, DE = 0xD000, GDMA dest = 0x9800 (or 0x9C00)
Frame N+1 (odd):  rows 8-15  → HL = 0xC2A0, DE = 0xD100, GDMA dest = 0x9900 (or 0x9D00)

Toggle byte stored at DF06 (0 or 1).

Total cycle cost per frame stays at R=8 level (~17K T).
Full 16-row coverage every 2 frames (~33ms at 60 FPS).
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


def create_stagger_attr_comp(bg_table_addr: int) -> bytes:
    """8-row attr_comp that toggles between row banks 0-7 and 8-15.

    On entry: A = bank (0 = rows 0-7, 1 = rows 8-15).
    Caller sets A from DF06 toggle before calling.
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()

    code.extend([0xC5, 0xD5, 0xE5, 0xF5])  # PUSH BC, DE, HL, AF

    # If A=1: HL = 0xC2A0 (offset +0x100), DE = 0xD100
    # If A=0: HL = 0xC1A0, DE = 0xD000
    # A in [0,1]; HL_hi = 0xC1 + A; DE_hi = 0xD0 + A
    code.extend([0xC6, 0xC1])              # ADD A, 0xC1 → A = HL_hi
    code.extend([0x67])                    # LD H, A
    code.extend([0x2E, 0xA0])              # LD L, 0xA0

    # DE_hi: A was = HL_hi (0xC1 or 0xC2); DE_hi = HL_hi - 0xC1 + 0xD0 = HL_hi + 0xF
    code.extend([0xC6, 0x0F])              # ADD A, 0x0F → A = DE_hi (0xD0 or 0xD1)
    code.extend([0x57])                    # LD D, A
    code.extend([0x1E, 0x00])              # LD E, 0x00

    code.extend([0x3E, 0x08])              # 8 rows
    code.extend([0xE0, 0xE0])              # LDH [FFE0], A

    row_loop = len(code)
    code.extend([0xF3])                    # DI
    code.extend([0x3E, 0x02, 0xE0, 0x70])  # FF70 = 2
    code.extend([0x06, bg_table_hi])       # B = bg_table_hi
    code.extend([0x3E, 0x18])              # A = 24

    tile_loop = len(code)
    code.extend([0xF5, 0x2A, 0x4F, 0x0A, 0x12, 0x13, 0xF1, 0x3D])
    code.extend([0x20, (tile_loop - (len(code) + 2)) & 0xFF])

    code.extend([0x3E, 0x01, 0xE0, 0x70])  # FF70 = 1
    code.extend([0xFB])                    # EI
    code.extend([0x7B, 0xC6, 0x08, 0x5F, 0x30, 0x01, 0x14])  # DE += 8

    code.extend([0xF0, 0xE0])
    code.extend([0x3D])
    code.extend([0xE0, 0xE0])
    code.extend([0x20, (row_loop - (len(code) + 2)) & 0xFF])

    code.extend([0xF1, 0xE1, 0xD1, 0xC1])
    code.extend([0xC9])
    return bytes(code)


def create_stagger_gdma() -> bytes:
    """GDMA: source = D000 or D100 (8 rows × 32 bytes = 256), dest = 0x9800 or 0x9900.

    On entry: A = bank (0 or 1). Caller sets A from DF06.
    GDMA bytes = 256 = 8 rows × 32. HDMA5 = (256/16) - 1 = 0x0F.
    """
    code = bytearray()
    code.extend([0xF5])                    # PUSH AF (save bank)
    code.extend([0xF3])                    # DI
    code.extend([0x3E, 0x01, 0xE0, 0x4F])  # VBK = 1
    code.extend([0x3E, 0x02, 0xE0, 0x70])  # FF70 = 2

    # HDMA src high = 0xD0 + A
    code.extend([0xF1])                    # POP AF (A = bank)
    code.extend([0xF5])                    # PUSH AF (save for dest calc)
    code.extend([0xC6, 0xD0])              # ADD A, 0xD0
    code.extend([0xE0, 0x51])              # HDMA1 = A
    code.extend([0xAF, 0xE0, 0x52])        # HDMA2 = 0x00

    # HDMA dest = tilemap_base + bank
    code.extend([0xF0, 0x40])              # LDH A,[LCDC]
    code.extend([0xE6, 0x08])              # AND 0x08
    code.extend([0x28, 0x04])              # JR Z, +4
    code.extend([0x3E, 0x9C])
    code.extend([0x18, 0x02])
    code.extend([0x3E, 0x98])              # base = 0x98 or 0x9C
    code.extend([0x47])                    # B = base
    code.extend([0xF1])                    # POP AF (A = bank, 0 or 1)
    code.extend([0x80])                    # A += B (dest_hi = base + bank)
    code.extend([0xE0, 0x53])              # HDMA3 = dest_hi
    code.extend([0xAF, 0xE0, 0x54])        # HDMA4 = 0x00

    code.extend([0x3E, 0x0F, 0xE0, 0x55])  # HDMA5 = 0x0F → 256 bytes general-mode

    code.extend([0x3E, 0x01, 0xE0, 0x70])  # FF70 = 1
    code.extend([0xAF, 0xE0, 0x4F])        # VBK = 0
    code.extend([0xFB])                    # EI
    code.extend([0xC9])
    return bytes(code)


def build():
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
    w(A['ac'], create_stagger_attr_comp(A['bt']))
    w(A['gd'], create_stagger_gdma())

    code = bytearray()
    code.extend([0xF0, 0x99, 0xF5, 0x3E, 0x0D, 0xE0, 0x99])
    code.extend([0xF0, 0x4F, 0xF5, 0xAF, 0xE0, 0x4F])
    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02 = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF])
    code.extend([0xAF, 0xEA, 0x00, 0xDF, 0xAF, 0xEA, 0x03, 0xDF])
    # Init stagger toggle at DF06 = 0
    code.extend([0xAF, 0xEA, 0x06, 0xDF])
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
    # Load stagger toggle, then call attr_comp(A)
    code.extend([0xFA, 0x06, 0xDF])        # LD A,[DF06]
    code.extend([0xF5])                    # PUSH AF (save bank)
    code.extend([0xCD, A['ac'] & 0xFF, (A['ac'] >> 8) & 0xFF])
    code.extend([0xF1])                    # POP AF (restore bank)
    code.extend([0xCD, A['gd'] & 0xFF, (A['gd'] >> 8) & 0xFF])
    # Toggle DF06: A = NOT A (since A in [0,1], XOR 1 flips)
    code.extend([0xFA, 0x06, 0xDF])
    code.extend([0xEE, 0x01])              # XOR 1
    code.extend([0xEA, 0x06, 0xDF])
    code[fg] = (len(code) - fg - 1) & 0xFF
    code.extend([0xF1, 0xE0, 0x4F, 0xF1, 0xE0, 0x99, 0xC9])
    w(A['cz'], bytes(code))
    print(f"  stagger colorize handler: {len(code)} bytes")

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
    out = Path("rom/working/penta_dragon_dx_v301_stagger.gb")
    out.write_bytes(rom)
    print(f"Wrote {out}")


if __name__ == "__main__":
    build()
