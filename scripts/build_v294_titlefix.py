#!/usr/bin/env python3
"""Penta Dragon DX v2.94 — title-screen BG attrs without trampoline.

Builds on top of v2.90's solid VBlank-only architecture (which proved best
for phantom-sound resilience: 6 D887 transitions vs vanilla 12). Adds:

1. cond_pal CALL moved BEFORE the FFC1=0 fast-exit gate — palettes load on
   title (FFC1=0), not just gameplay (FFC1=1).
2. bg_sweep INTERNAL FFC1=0 check removed — sweep runs on every frame
   including title, so title BG tile attributes get written.

This avoids v2.87/v2.89's trampoline (which caused phantom-sound regression
by writing FF99 mid-frame, conflicting with the Timer-ISR's FF99-based bank
restore on RETI).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_tile_to_palette_subroutine, create_bg_tile_table,
)
from create_vblank_colorizer_v288 import create_conditional_palette_cached


def create_bg_sweep_v8_no_menu_skip(bg_table_addr: int, base_addr: int) -> bytes:
    """Same as build_v290_final.create_bg_sweep_v8 but without the FFC1=0
    early-exit. Letting the sweep run on the title screen writes the BG
    attributes there so the title renders with the loaded palette.

    Cost: ~2200 T-cycles per VBlank on title (vs current 0). VBlank period
    is 4560 T, so plenty of headroom on the otherwise-idle title screen.
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    s = bytearray()

    # NO menu skip (was: LDH A,[FFC1]; OR A; RET Z = F0 C1 B7 C8)
    # Title-screen sweep is the whole point of this build.
    s.extend([0xC5, 0xD5, 0xE5])  # save regs (BC, DE, HL)

    # base_hi from LCDC bit 3
    s.extend([0xF0, 0x40, 0xE6, 0x08, 0x0F, 0xC6, 0x98, 0xEA, 0x01, 0xDF])

    # Edge priority: detect scroll direction
    s.extend([0xF0, 0x42, 0xCB, 0x3F, 0xCB, 0x3F, 0xCB, 0x3F, 0x47])  # B = SCY/8

    # Increment DF04 (row counter) and clamp 0..17
    s.extend([0xFA, 0x04, 0xDF, 0x3C, 0xFE, 0x12, 0x20, 0x02, 0x3E, 0x00])
    s.extend([0xEA, 0x04, 0xDF, 0x4F])  # C = current row

    # Compute tilemap_row_addr = base_hi:00 + (B+C)*32 (B=scroll, C=row 0..17)
    s.extend([0x81])              # A = B+C  (scroll + row)
    s.extend([0xE6, 0x1F])        # AND 0x1F (mod 32 tile rows)
    s.extend([0x87, 0x87, 0x87, 0x87, 0x87])  # A *= 32
    s.extend([0x6F])              # L = A
    s.extend([0xFA, 0x01, 0xDF, 0x67])  # H = base_hi
    s.extend([0x11, 0x10, 0xDF])  # DE = DF10 (buffer)

    # Phase 1: read 32 tile IDs from tilemap (VBK=0) into DF10-DF2F
    s.extend([0xAF, 0xE0, 0x4F])  # VBK=0
    s.extend([0x06, 0x20])        # B = 32
    s.extend([0x2A, 0x12, 0x13])  # A = [HL+], [DE] = A, INC DE
    s.extend([0x05, 0x20, 0xFA])  # DEC B; JR NZ
    # restore HL to row base after reading 32 tiles
    s.extend([0x7D, 0xD6, 0x20, 0x6F, 0x30, 0x02, 0x25])  # L -= 32; if borrow H--

    # Phase 2: lookup palette for each tile via bg_table (still VBK=0)
    s.extend([0x11, 0x10, 0xDF])  # DE = DF10 (buffer pointer)
    s.extend([0x06, 0x20])        # B = 32 (count)
    # loop body: A = [DE]; HL = bg_table_addr + A; A = [HL]; [DE] = A; INC DE; DEC B; JR NZ
    s.extend([0x1A])              # A = [DE]
    s.extend([0x21, 0x00, bg_table_hi])  # HL = bg_table_addr
    s.extend([0x85, 0x6F])        # L += A
    s.extend([0x30, 0x01, 0x24])  # if carry, H++
    s.extend([0x7E, 0x12, 0x13])  # A = [HL]; [DE] = A; INC DE
    s.extend([0x05, 0x20, 0xF1])  # DEC B; JR NZ -15

    # Phase 3: write palette attributes (VBK=1, palette bits 0-2)
    s.extend([0x3E, 0x01, 0xE0, 0x4F])  # VBK=1
    s.extend([0xFA, 0x01, 0xDF, 0x67])  # H = base_hi
    s.extend([0x7D, 0xD6, 0x20, 0x6F, 0x30, 0x02, 0x25])  # L = row base, restore
    s.extend([0x11, 0x10, 0xDF, 0x06, 0x20])  # DE = DF10 ; B = 32
    s.extend([0x1A, 0x22])        # A = [DE], [HL+] = A
    s.extend([0x13])              # INC DE
    s.extend([0x05, 0x20, 0xFA])  # DEC B; JR NZ

    s.extend([0xAF, 0xE0, 0x4F])  # VBK=0 (restore)
    s.extend([0xE1, 0xD1, 0xC1])  # pop regs
    s.append(0xC9)                # RET

    return bytes(s)


def build_v294():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v294.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    rom = bytearray(input_rom.read_bytes())
    palettes = load_palettes_from_yaml(palette_yaml)

    # CGB flag
    rom[0x143] = 0x80

    # Bank-13 layout (identical to v290)
    bank13 = 13 * 0x4000
    pal_addr = 0x6800; boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0
    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    bg_table_addr = 0x7000
    cond_pal_addr = 0x6C90
    bg_sweep_addr = 0x6CD0
    colorize_addr = 0x6E00

    def w(addr, data):
        off = bank13 + (addr - 0x4000)
        rom[off:off + len(data)] = data

    # Palette/function data (identical to v290)
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
    colorizer[1] = 0x0A  # 10 sprites per page
    w(colorizer_addr, bytes(colorizer))

    w(tile_pal_addr, create_tile_to_palette_subroutine())
    w(bg_table_addr, create_bg_tile_table(ff_filter=False))
    w(cond_pal_addr, create_conditional_palette_cached(pal_loader_addr))

    # *** v294 change: bg_sweep variant without internal FFC1=0 RET Z ***
    sweep = create_bg_sweep_v8_no_menu_skip(bg_table_addr, bg_sweep_addr)
    w(bg_sweep_addr, sweep)

    # COLORIZE HANDLER:
    #   v290 order: VBK save → FFC1 check → DF02 init → cond_pal → bg_sweep → OBJ → DMA
    #   v294 order: VBK save → DF02 init → cond_pal (always) → bg_sweep (always)
    #               → FFC1 gate → OBJ colorizer → DMA → VBK restore
    code = bytearray()
    code.extend([0xF0, 0x4F, 0xF5, 0xAF, 0xE0, 0x4F])  # VBK save + VBK=0
    # DF02 cold-boot init
    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02 = len(code) + 1; code.extend([0x28, 0x00])
    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF,
                 0xAF, 0xEA, 0x00, 0xDF])
    code[df02] = (len(code) - df02 - 1) & 0xFF
    # cond_pal — ALWAYS (so title gets palettes loaded)
    code.extend([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])
    # bg_sweep — ALWAYS (so title gets BG attributes written)
    code.extend([0xCD, bg_sweep_addr & 0xFF, (bg_sweep_addr >> 8) & 0xFF])
    # FFC1 gate for OBJ colorizer only (sprites are gameplay-only)
    code.extend([0xF0, 0xC1, 0xB7])
    skip = len(code) + 1; code.extend([0x28, 0x00])
    code.extend([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    code[skip] = (len(code) - skip - 1) & 0xFF
    code.extend([0xCD, 0x80, 0xFF])                    # DMA
    code.extend([0xF1, 0xE0, 0x4F, 0xC9])              # VBK restore + RET
    w(colorize_addr, bytes(code))

    # VBlank hook (identical to v290 — inline joypad + bank-13 CALL)
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
    assert len(hook) <= 47
    rom[0x0824:0x0824 + 47] = (hook + bytearray(47 - len(hook)))[:47]
    rom[0x06D5:0x06D8] = bytearray([0x00, 0x00, 0x00])  # NOP original DMA

    # Phantom-sound belt-and-suspenders patch
    rom[0x003B] = 0xC9  # RETI → RET

    # Header checksum
    chk = 0
    for b in rom[0x134:0x14D]:
        chk = (chk - b - 1) & 0xFF
    rom[0x14D] = chk

    output_path.write_bytes(rom)
    print(f"Wrote {output_path} ({len(rom)} bytes)")
    return output_path


if __name__ == "__main__":
    build_v294()
