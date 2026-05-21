#!/usr/bin/env python3
"""v3.01 unrolled attr_comp: eliminate PUSH AF/POP AF/DEC/JR per tile.

Original tile loop per tile:
  PUSH AF (16T) + LD A,[HL+] (8T) + LD C,A (4T) + LD A,[BC] (8T)
  + LD [DE],A (8T) + INC DE (8T) + POP AF (12T) + DEC A (4T)
  + JR NZ (8/12T)
  = ~80T per tile × 24 = 1920T per row

Unrolled (24 explicit tile reads, no PUSH/POP/loop machinery):
  LD A,[HL+] (8T) + LD C,A (4T) + LD A,[BC] (8T)
  + LD [DE],A (8T) + INC DE (8T)
  = 36T per tile × 24 = 864T per row

Saves ~1050T per row. With 18 rows: ~19K T saved → fits in budget.

Code size: 24 × 5 = 120 bytes per unrolled tile sequence × 1 (reused
for each row in outer loop) = 120 bytes + outer loop ~30 bytes = 150 bytes.
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


def create_attr_comp_unrolled(bg_table_addr: int, n_rows: int, base_addr: int) -> bytes:
    """attr_comp with fully unrolled inner 24-tile loop.

    base_addr: absolute address where this code will be placed (for JP back-branch).
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()

    code.extend([0xC5, 0xD5, 0xE5, 0xF5])  # PUSH BC, DE, HL, AF
    code.extend([0x21, 0xA0, 0xC1])         # LD HL, 0xC1A0
    code.extend([0x11, 0x00, 0xD0])         # LD DE, 0xD000
    code.extend([0x3E, n_rows])             # row count
    code.extend([0xE0, 0xE0])               # LDH [FFE0], A

    row_loop = len(code)
    row_loop_abs = base_addr + row_loop
    code.extend([0xF3])                     # DI
    code.extend([0x3E, 0x02, 0xE0, 0x70])   # FF70 = 2
    code.extend([0x06, bg_table_hi])        # LD B, bg_table_hi

    # Unrolled 24-tile sequence (each tile: 5 bytes, 36T)
    for _ in range(24):
        code.extend([0x2A])                 # LD A,[HL+]
        code.extend([0x4F])                 # LD C, A
        code.extend([0x0A])                 # LD A,[BC]
        code.extend([0x12])                 # LD [DE], A
        code.extend([0x13])                 # INC DE

    code.extend([0x3E, 0x01, 0xE0, 0x70])   # FF70 = 1
    code.extend([0xFB])                     # EI

    # DE += 8 (stride)
    code.extend([0x7B, 0xC6, 0x08, 0x5F, 0x30, 0x01, 0x14])

    # Row counter — use JP for absolute back-branch (JR -146 would overflow)
    code.extend([0xF0, 0xE0])               # LDH A,[FFE0]
    code.extend([0x3D])                     # DEC A
    code.extend([0xE0, 0xE0])               # LDH [FFE0],A
    code.extend([0x28, 0x03])               # JR Z, +3 (skip JP)
    code.extend([0xC3, row_loop_abs & 0xFF, (row_loop_abs >> 8) & 0xFF])  # JP row_loop_abs

    code.extend([0xF1, 0xE1, 0xD1, 0xC1])
    code.extend([0xC9])
    return bytes(code)


def create_gdma_general() -> bytes:
    code = bytearray()
    code.extend([0xF3])
    code.extend([0x3E, 0x01, 0xE0, 0x4F])
    code.extend([0x3E, 0x02, 0xE0, 0x70])
    code.extend([0x3E, 0xD0, 0xE0, 0x51])
    code.extend([0xAF, 0xE0, 0x52])
    code.extend([0xF0, 0x40])
    code.extend([0xE6, 0x08])
    code.extend([0x28, 0x04])
    code.extend([0x3E, 0x9C])
    code.extend([0x18, 0x02])
    code.extend([0x3E, 0x98])
    code.extend([0xE0, 0x53])
    code.extend([0xAF, 0xE0, 0x54])
    code.extend([0x3E, 0x3F, 0xE0, 0x55])
    code.extend([0x3E, 0x01, 0xE0, 0x70])
    code.extend([0xAF, 0xE0, 0x4F])
    code.extend([0xFB])
    code.extend([0xC9])
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
    ac_code = create_attr_comp_unrolled(A['bt'], n_rows, A['ac'])
    print(f"  unrolled attr_comp: {len(ac_code)} bytes ({n_rows} rows)")
    w(A['ac'], ac_code)
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
    out = Path(f"rom/working/penta_dragon_dx_v301_unroll_R{n_rows}.gb")
    out.write_bytes(rom)
    print(f"Wrote {out}")


if __name__ == "__main__":
    n = int(sys.argv[1])
    build(n)
