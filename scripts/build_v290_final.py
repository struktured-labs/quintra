#!/usr/bin/env python3
"""
Penta Dragon DX v2.90 — Final Build Script

Architecture: Inline joypad + Bank 13 colorize call
- Joypad read stays inline at 0x0824 (original code location, trimmed to fit)
- Bank 13 colorize handler: cond_pal + bg_sweep + OBJ colorizer + DMA
- No trampoline (causes D887 corruption via FF99/Timer ISR interaction)
- MiSTer requires "Audio mode = No Pops" in Gameboy core OSD settings

Verified metrics (mgba automated):
- D887: 0 GARBAGE events
- Speed: 147 SCY changes (identical to original)
- Game state: D880 advances to 0x02 (dungeon gameplay)
- Colors: walls gray, floor blue, items distinct palettes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_tile_to_palette_subroutine, create_bg_tile_table,
)
from create_vblank_colorizer_v288 import create_conditional_palette_cached


def create_bg_sweep_v8(bg_table_addr: int, base_addr: int) -> bytes:
    """Batched VBK sweep with direction-aware edge priority.
    
    1 row per call, VBK toggled 3x per row (not per tile).
    Three phases: read tiles (VBK=0) → lookup palettes → write attrs (VBK=1).
    Uses DF10-DF2F as 32-byte WRAM buffer.
    ~2200 T-cycles per row (vs ~4500 with per-tile VBK toggle).
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    s = bytearray()
    
    # Skip menus
    s.extend([0xF0, 0xC1, 0xB7, 0xC8])
    s.extend([0xC5, 0xD5, 0xE5])  # save regs
    
    # base_hi from LCDC bit 3
    s.extend([0xF0, 0x40, 0xE6, 0x08, 0x0F, 0xC6, 0x98, 0xEA, 0x01, 0xDF])
    
    # Edge priority: detect scroll direction
    s.extend([0xF0, 0x42, 0xCB, 0x3F, 0xCB, 0x3F, 0xCB, 0x3F, 0x47])  # B=SCY/8
    s.extend([0xF0, 0xA9, 0xB8])  # compare with prev
    jr_ns = len(s) + 1; s.extend([0x28, 0x00])  # JR Z no_scroll
    s.extend([0x78, 0xF0, 0xA9, 0x90, 0xFE, 0x10])  # diff, CP 16
    jr_up = len(s) + 1; s.extend([0x30, 0x00])  # JR NC scroll_up
    s.extend([0x3E, 17])  # scroll DOWN: DF04=17 (bottom edge)
    jr_set = len(s) + 1; s.extend([0x18, 0x00])  # JR set_df04
    s[jr_up] = (len(s) - jr_up - 1) & 0xFF
    s.extend([0xAF])  # scroll UP: DF04=0 (top edge)
    s[jr_set] = (len(s) - jr_set - 1) & 0xFF
    s.extend([0xEA, 0x04, 0xDF])  # set DF04
    s[jr_ns] = (len(s) - jr_ns - 1) & 0xFF
    s.extend([0x78, 0xE0, 0xA9])  # save SCY/8
    
    # 1 row (batched)
    s.extend([0x0E, 0x01])  # LD C, 1
    outer = len(s)
    
    # Compute tilemap_row and VRAM address
    s.extend([0xF0, 0x42, 0xCB, 0x3F, 0xCB, 0x3F, 0xCB, 0x3F, 0x47])
    s.extend([0xFA, 0x04, 0xDF, 0x80, 0xE6, 0x1F])
    s.extend([0x47, 0xCB, 0x3F, 0xCB, 0x3F, 0xCB, 0x3F, 0x57])
    s.extend([0xFA, 0x01, 0xDF, 0x82, 0x57])
    s.extend([0x78, 0xE6, 0x07, 0xCB, 0x37, 0x87, 0x5F])
    
    # Save BC, DE for phases
    s.extend([0xC5, 0xD5])
    
    # Phase 1: VBK=0, read 32 tiles → DF10, lookup palettes
    s.extend([0xAF, 0xE0, 0x4F])
    s.extend([0x06, 0x20, 0x21, 0x10, 0xDF])
    p1 = len(s)
    s.extend([0x1A, 0xD5, 0x16, bg_table_hi, 0x5F, 0x1A, 0xD1, 0x22, 0x1C, 0x05])
    s.extend([0x20, (p1 - len(s) - 2) & 0xFF])
    
    # Phase 2: VBK=1, write 32 attrs to active tilemap
    s.extend([0xD1])  # POP DE (VRAM start)
    s.extend([0x3E, 0x01, 0xE0, 0x4F])
    s.extend([0x21, 0x10, 0xDF, 0x06, 0x20])
    p2 = len(s)
    s.extend([0x2A, 0x12, 0x1C, 0x05])
    s.extend([0x20, (p2 - len(s) - 2) & 0xFF])
    
    # Phase 3: write to other tilemap
    s.extend([0x7B, 0xD6, 0x20, 0x5F])  # E -= 32
    s.extend([0x7A, 0xEE, 0x04, 0x57])  # D ^= 4
    s.extend([0x21, 0x10, 0xDF, 0x06, 0x20])
    p3 = len(s)
    s.extend([0x2A, 0x12, 0x1C, 0x05])
    s.extend([0x20, (p3 - len(s) - 2) & 0xFF])
    
    # VBK=0, restore BC
    s.extend([0xAF, 0xE0, 0x4F, 0xC1])
    
    # Advance DF04
    s.extend([0xFA, 0x04, 0xDF, 0x3C, 0xFE, 24])
    jr = len(s) + 1; s.extend([0x38, 0x00])
    s.extend([0xAF]); s[jr] = (len(s) - jr - 1) & 0xFF
    s.extend([0xEA, 0x04, 0xDF])
    
    # Outer loop
    s.extend([0x0D, 0x20, (outer - len(s) - 2) & 0xFF])
    s.extend([0xE1, 0xD1, 0xC1, 0xC9])
    
    return bytes(s)


def build_v290():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v290.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")
    
    rom = bytearray(input_rom.read_bytes())
    rom[0x143] = 0x80  # CGB flag
    
    palettes = load_palettes_from_yaml(palette_yaml)
    bank13 = 13 * 0x4000
    
    # Address layout in bank 13
    pal_addr = 0x6800
    boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
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
    
    # Write palette data
    w(pal_addr, palettes['bg_data'])
    w(pal_addr + 64, palettes['obj_data'])
    w(boss_pal_addr, palettes['boss_palette_table'])
    w(boss_slot_addr, palettes['boss_slot_table'])
    w(swj_addr, palettes['sara_witch_jet'])
    w(sdj_addr, palettes['sara_dragon_jet'])
    w(sp_addr, palettes['spiral_proj'])
    w(shp_addr, palettes['shield_proj'])
    w(tp_addr, palettes['turbo_proj'])
    
    # Write functions
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
    
    sweep = create_bg_sweep_v8(bg_table_addr, bg_sweep_addr)
    w(bg_sweep_addr, sweep)
    
    # Colorize handler (no joypad — stays inline at 0x0824)
    code = bytearray()
    code.extend([0xF0, 0x4F, 0xF5, 0xAF, 0xE0, 0x4F])  # VBK save
    code.extend([0xF0, 0xC1, 0xB7])
    skip = len(code) + 1; code.extend([0x28, 0x00])  # JR Z → DMA
    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02 = len(code) + 1; code.extend([0x28, 0x00])
    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF, 0xAF, 0xEA, 0x00, 0xDF])
    code[df02] = (len(code) - df02 - 1) & 0xFF
    code.extend([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])
    code.extend([0xCD, bg_sweep_addr & 0xFF, (bg_sweep_addr >> 8) & 0xFF])
    code.extend([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    code[skip] = (len(code) - skip - 1) & 0xFF
    code.extend([0xCD, 0x80, 0xFF])  # DMA
    code.extend([0xF1, 0xE0, 0x4F, 0xC9])
    w(colorize_addr, bytes(code))
    
    # VBlank hook: inline joypad + bank 13 colorize
    hook = bytearray([
        0xF0, 0x99, 0xF5,  # save bank from FF99 (3)
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00,  # P14 select+read (6)
        0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,  # P14 process (6)
        0x3E, 0x10, 0xE0, 0x00,  # P13 select (4)
        0xF0, 0x00, 0xF0, 0x00,  # P13 reads (4)
        0x2F, 0xE6, 0x0F, 0xB0, 0xE0, 0x93,  # P13 process+store (6)
        0x3E, 0x30, 0xE0, 0x00,  # deselect (4)
        0x3E, 0x0D, 0xEA, 0x00, 0x20,  # bank 13 (5)
        0xCD, colorize_addr & 0xFF, (colorize_addr >> 8) & 0xFF,  # CALL (3)
        0xF1, 0xEA, 0x00, 0x20,  # restore bank (4)
        0xC9,  # RET (1)
    ])
    assert len(hook) <= 47, f"Hook is {len(hook)} bytes, max 47"
    rom[0x0824:0x0824 + 47] = (hook + bytearray(47 - len(hook)))[:47]
    
    # NOP original DMA (our handler does it)
    rom[0x06D5:0x06D8] = bytearray([0x00, 0x00, 0x00])
    
    # Header checksum
    x = 0
    for i in range(0x134, 0x14D):
        x = (x - rom[i] - 1) & 0xFF
    rom[0x14D] = x
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rom)
    
    print(f"Built v2.90: {output_path}")
    print(f"  Sweep: {len(sweep)} bytes (batched VBK, 1 row/frame, edge priority)")
    print(f"  Colorize: {len(code)} bytes")
    print(f"  Hook: {len(hook)} bytes (inline joypad + bank 13 call)")
    return output_path


if __name__ == "__main__":
    build_v290()
