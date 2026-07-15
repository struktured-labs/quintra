#!/usr/bin/env python3
"""v3.01 with attr_computation ENABLED — sanity-check the diagnosis.

Same as build_v301_gdma.py except attr_computation is called inside the
FFC1 gate (not skipped). Per the diagnosis this should freeze at FFC1=0→1.
Reproducing the failure confirms we're testing the right thing.

Output: rom/working/penta_dragon_dx_v301_attr_enabled.gb
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_tile_to_palette_subroutine,
)
from create_vblank_colorizer_v288 import create_conditional_palette_cached
from build_v296_phantomsafe import create_bg_sweep_viewport_gated
from build_v301_gdma import (
    BG_TABLE_BYTES, WRAM_BG_TABLE,
    create_inline_tile_copy_tileonly,
    create_gdma_transfer, create_attr_computation,
)


def build():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v301_attr_enabled.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    rom = bytearray(input_rom.read_bytes())
    palettes = load_palettes_from_yaml(palette_yaml)
    bg_data = bytearray(palettes['bg_data'])
    bg_data[56:64] = bg_data[0:8]
    palettes = {**palettes, 'bg_data': bytes(bg_data)}
    rom[0x143] = 0x80

    bank13 = 13 * 0x4000
    pal_addr = 0x6800
    boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0
    pal_loader_addr = 0x6900; shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10; tile_pal_addr = 0x6B00
    cond_pal_addr = 0x6C90; bg_sweep_addr = 0x6CD0
    gdma_addr = 0x6D80; colorize_addr = 0x6E00
    bg_table_addr = 0x7000; attr_comp_addr = 0x7100

    def w(addr, data):
        off = bank13 + (addr - 0x4000)
        rom[off:off + len(data)] = data

    w(pal_addr, palettes['bg_data'])
    w(pal_addr + 64, palettes['obj_data'])
    w(boss_pal_addr, palettes['boss_palette_table'])
    w(boss_slot_addr, palettes['boss_slot_table'])
    w(swj_addr, palettes['sara_witch_jet'])
    w(sdj_addr, palettes['sara_dragon_jet'])
    w(sp_addr, palettes['spiral_proj'])
    w(shp_addr, palettes['shield_proj'])
    w(tp_addr, palettes['turbo_proj'])
    w(pal_loader_addr, create_palette_loader(
        pal_addr, boss_pal_addr, boss_slot_addr,
        swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr))
    w(shadow_main_addr, create_shadow_colorizer_main(colorizer_addr, boss_slot_addr))
    colorizer = bytearray(create_tile_based_colorizer(colorizer_addr))
    colorizer[1] = 0x0A
    w(colorizer_addr, bytes(colorizer))
    w(tile_pal_addr, create_tile_to_palette_subroutine())
    w(bg_table_addr, BG_TABLE_BYTES)
    w(cond_pal_addr, create_conditional_palette_cached(pal_loader_addr))

    sweep = bytearray(create_bg_sweep_viewport_gated(bg_table_addr, bg_sweep_addr))
    assert sweep[:4] == bytearray([0xF0, 0xC1, 0xB7, 0xC8])
    sweep[0:4] = bytearray([0x00, 0x00, 0x00, 0x00])
    w(bg_sweep_addr, bytes(sweep))

    w(gdma_addr, create_gdma_transfer())
    attr_comp = create_attr_computation(bg_table_addr)
    w(attr_comp_addr, attr_comp)

    code = bytearray()
    code.extend([0xF0, 0x4F, 0xF5])
    code.extend([0xAF, 0xE0, 0x4F])

    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02_jr = len(code) + 1
    code.extend([0x28, 0x00])

    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF])
    code.extend([0xAF, 0xEA, 0x00, 0xDF])
    code.extend([0xAF, 0xEA, 0x03, 0xDF])
    code.extend([0x21, bg_table_addr & 0xFF, (bg_table_addr >> 8) & 0xFF])
    code.extend([0x11, WRAM_BG_TABLE & 0xFF, (WRAM_BG_TABLE >> 8) & 0xFF])
    code.extend([0x06, 0x00])
    bg_copy = len(code)
    code.extend([0x2A, 0x12, 0x13, 0x05])
    offset = bg_copy - (len(code) + 2)
    code.extend([0x20, offset & 0xFF])
    code[df02_jr] = (len(code) - df02_jr - 1) & 0xFF

    code.extend([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])
    code.extend([0xCD, bg_sweep_addr & 0xFF, (bg_sweep_addr >> 8) & 0xFF])

    code.extend([0xFA, 0x03, 0xDF, 0xB7])
    gdma_skip = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0xCD, gdma_addr & 0xFF, (gdma_addr >> 8) & 0xFF])
    code[gdma_skip] = (len(code) - gdma_skip - 1) & 0xFF

    code.extend([0xF0, 0xC1, 0xB7])
    ffc1_skip = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0xCD, 0x80, 0xFF])
    code.extend([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    # ── attr_computation ENABLED ──
    code.extend([0xCD, attr_comp_addr & 0xFF, (attr_comp_addr >> 8) & 0xFF])
    # Set DF03=1 so GDMA picks up the buffer next frame
    code.extend([0x3E, 0x01, 0xEA, 0x03, 0xDF])
    code[ffc1_skip] = (len(code) - ffc1_skip - 1) & 0xFF

    code.extend([0xF1, 0xE0, 0x4F])
    code.extend([0xC9])

    w(colorize_addr, bytes(code))
    print(f"  colorize handler: {len(code)} bytes (attr_computation ENABLED)")

    hook = bytearray([
        0xF0, 0x99, 0xF5,
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00,
        0xF0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xB0, 0xE0, 0x93,
        0x3E, 0x30, 0xE0, 0x00,
        0x3E, 0x0D, 0xEA, 0x00, 0x20,
        0xCD, colorize_addr & 0xFF, (colorize_addr >> 8) & 0xFF,
        0xF1, 0xEA, 0x00, 0x20,
        0xC9,
    ])
    rom[0x0824:0x0824 + 47] = (hook + bytearray(47 - len(hook)))[:47]
    rom[0x06D5:0x06D8] = bytearray([0x00, 0x00, 0x00])
    rom[0x003B] = 0xC9

    inline_code = create_inline_tile_copy_tileonly()
    available = 0x436D - 0x42A7 + 1
    rom[0x42A7:0x42A7 + len(inline_code)] = inline_code
    if len(inline_code) < available:
        rom[0x42A7 + len(inline_code):0x436E] = bytearray(available - len(inline_code))

    chk = 0
    for b in rom[0x134:0x14D]:
        chk = (chk - b - 1) & 0xFF
    rom[0x14D] = chk

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rom)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    build()
