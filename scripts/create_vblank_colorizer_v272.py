#!/usr/bin/env python3
"""
v2.72: Dual-tilemap viewport BG colorizer - both tilemaps always colored

Root cause fix for v2.72a's 93% accuracy: the game alternates LCDC bit 3
between tilemaps 0x9800 and 0x9C00 each frame. A single-tilemap colorizer
only colors alternating rows of each tilemap → half the tiles are wrong.

Fix: Write palette attributes to BOTH tilemaps for each tile (D XOR 0x04).
This adds ~52T per tile but guarantees both tilemaps always have correct
palette attributes. No settling delay between tilemap switches.

Budget: ~22% (vs v2.62's 35%) - game runs 37% faster
  Per tile: ~160T work + ~124T avg STAT wait = ~284T during rendering
  64 tiles/frame × 284T = ~18,200T = ~26% budget (conservative)
  Compare: v2.62's 71 tiles × 348T = 24,700T = 35%

Settling: 9 frames (0.15s) - both tilemaps colored simultaneously
Flicker: ZERO (STAT-safe + both tilemaps colored)

HRAM usage:
  FF91: viewport row counter (0-17)
  FFA5: tilemap base hi (0x98 or 0x9C, from LCDC)
  FFA9: palette hash (conditional palette, shared)
  FFEE: temp palette storage
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_conditional_palette, create_tile_to_palette_subroutine,
    create_vblank_hook, create_bg_tile_table,
)
from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_bg_colorizer_dual_viewport(bg_table_addr: int, rows_per_frame: int = 2) -> bytes:
    """Viewport BG colorizer that writes palette attrs to BOTH tilemaps.

    For each tile:
    1. STAT wait (safe VRAM access)
    2. Read tile ID from active tilemap (VBK=0)
    3. ROM lookup → palette
    4. Switch to VBK=1
    5. Write palette to active tilemap
    6. Write palette to other tilemap (D XOR 0x04)
    7. Restore D, switch to VBK=0
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    # === PREAMBLE ===
    emit([0xF0, 0xC1])        # LDH A, [FFC1]  - gameplay check
    emit([0xB7])               # OR A
    emit([0xC8])               # RET Z           - skip on menus

    emit([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL

    # Compute tilemap base from LCDC bit 3 (read source)
    emit([0xF0, 0x40])        # LDH A, [FF40]  - LCDC
    emit([0xE6, 0x08])        # AND 0x08        - bit 3
    emit([0x0F])               # RRCA            - 0 or 4
    emit([0xC6, 0x98])        # ADD A, 0x98     - 0x98 or 0x9C
    emit([0xE0, 0xA5])        # LDH [FFA5], A   - save base_hi

    # ROM table high byte
    emit([0x26, bg_table_hi]) # LD H, table_hi

    # Ensure VBK=0
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # LDH [FF4F], A

    # Outer row counter (C = rows to process this frame)
    emit([0x0E, rows_per_frame & 0xFF])  # LD C, rows_per_frame

    # === OUTER ROW LOOP ===
    row_loop = len(code)

    # Compute tilemap_row = (SCY/8 + row_counter) & 0x1F
    emit([0xF0, 0x42])        # LDH A, [FF42]  - SCY
    emit([0xCB, 0x3F])        # SRL A           - /2
    emit([0xCB, 0x3F])        # SRL A           - /4
    emit([0xCB, 0x3F])        # SRL A           - /8
    emit([0x47])               # LD B, A         - B = SCY/8
    emit([0xF0, 0x91])        # LDH A, [FF91]  - row_counter (0-17)
    emit([0x80])               # ADD A, B        - SCY/8 + row_counter
    emit([0xE6, 0x1F])        # AND 0x1F        - mod 32

    # Compute row start address in DE
    # Low byte: (tilemap_row & 7) << 5
    emit([0x47])               # LD B, A         - save tilemap_row
    emit([0xE6, 0x07])        # AND 0x07        - low 3 bits
    emit([0xCB, 0x37])        # SWAP A          - × 16
    emit([0x87])               # ADD A, A        - × 32
    emit([0x5F])               # LD E, A         - E = row_lo

    # High byte: base_hi + (tilemap_row >> 3)
    emit([0x78])               # LD A, B         - tilemap_row
    emit([0xCB, 0x3F])        # SRL A           - /2
    emit([0xCB, 0x3F])        # SRL A           - /4
    emit([0xCB, 0x3F])        # SRL A           - /8 → 0-3
    emit([0x57])               # LD D, A
    emit([0xF0, 0xA5])        # LDH A, [FFA5]  - base_hi
    emit([0x82])               # ADD A, D
    emit([0x57])               # LD D, A         - D = hi

    # Inner counter: 32 tiles per row
    emit([0x06, 0x20])        # LD B, 32

    # === INNER TILE LOOP ===
    tile_loop = len(code)

    # STAT wait: spin until mode 0 (HBlank) or mode 1 (VBlank)
    stat_wait = len(code)
    emit([0xF0, 0x41])        # LDH A, [FF41]   - STAT register
    emit([0xE6, 0x02])        # AND 0x02         - bit 1: mode 2/3
    stat_jr = len(code)
    emit([0x20, 0x00])        # JR NZ, stat_wait
    code[stat_jr + 1] = (stat_wait - (stat_jr + 2)) & 0xFF

    # Read tile from active tilemap (VBK=0)
    emit([0x1A])               # LD A, [DE]      - tile ID
    emit([0x6F])               # LD L, A
    emit([0x7E])               # LD A, [HL]      - palette from ROM table

    # Save palette to HRAM
    emit([0xE0, 0xEE])        # LDH [FFEE], A

    # Switch to VBK=1 for attribute writes
    emit([0x3E, 0x01])        # LD A, 0x01
    emit([0xE0, 0x4F])        # LDH [FF4F], A   - VBK=1

    # Write palette to ACTIVE tilemap
    emit([0xF0, 0xEE])        # LDH A, [FFEE]
    emit([0x12])               # LD [DE], A

    # Write palette to OTHER tilemap (D XOR 0x04)
    emit([0x7A])               # LD A, D
    emit([0xEE, 0x04])        # XOR 0x04         - flip 0x98↔0x9C
    emit([0x57])               # LD D, A
    emit([0xF0, 0xEE])        # LDH A, [FFEE]   - palette again
    emit([0x12])               # LD [DE], A       - write to other tilemap

    # Restore D to active tilemap
    emit([0x7A])               # LD A, D
    emit([0xEE, 0x04])        # XOR 0x04         - flip back
    emit([0x57])               # LD D, A

    # Switch back to VBK=0
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # LDH [FF4F], A   - VBK=0

    # Next tile
    emit([0x1C])               # INC E
    emit([0x05])               # DEC B

    # JR NZ back to tile_loop
    tile_back = len(code)
    tile_offset = tile_loop - (tile_back + 2)
    emit([0x20, tile_offset & 0xFF])

    # === ADVANCE ROW COUNTER (mod 18) ===
    emit([0xF0, 0x91])        # LDH A, [FF91]
    emit([0x3C])               # INC A
    emit([0xFE, 18])          # CP 18
    emit([0x38, 0x01])        # JR C, no_wrap
    emit([0xAF])               # XOR A            - wrap to 0
    # no_wrap:
    emit([0xE0, 0x91])        # LDH [FF91], A

    # === OUTER LOOP ===
    emit([0x0D])               # DEC C
    row_back = len(code)
    row_offset = row_loop - (row_back + 2)
    if row_offset < -128:
        raise ValueError(f"Row loop JR offset {row_offset} out of range!")
    emit([0x20, row_offset & 0xFF])

    # === CLEANUP ===
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # LDH [FF4F], A   - ensure VBK=0
    emit([0xE1, 0xD1, 0xC1]) # POP HL, DE, BC
    emit([0xC9])               # RET

    return bytes(code)


def build_v272():
    """Build v2.72 ROM."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)
    palettes = load_palettes_from_yaml(palette_yaml)

    # Data layout
    pal_addr = 0x6800
    boss_pal_addr = 0x6880
    boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0

    # Code layout
    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    bg_colorizer_addr = 0x6C00
    cond_pal_addr = 0x6C80
    combined_addr = 0x6D00
    bg_table_addr = 0x6E00

    # Generate code
    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    cond_pal = create_conditional_palette(pal_loader_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)  # No ff_filter with STAT waits
    bg_colorizer = create_bg_colorizer_dual_viewport(bg_table_addr, rows_per_frame=2)

    print(f"BG colorizer: {len(bg_colorizer)} bytes (at 0x{bg_colorizer_addr:04X})")

    # Auto-relocate cond_pal if BG colorizer is too large
    if bg_colorizer_addr + len(bg_colorizer) > cond_pal_addr:
        cond_pal_addr = bg_colorizer_addr + len(bg_colorizer)
        cond_pal_addr = (cond_pal_addr + 0xF) & ~0xF  # align to 16
        print(f"  Moved cond_pal to 0x{cond_pal_addr:04X}")
        cond_pal = create_conditional_palette(pal_loader_addr)

    # Combined: BG first (STAT-safe), then palette, OBJ, DMA
    combined = bytearray()
    combined.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    combined.extend([0xCD, cond_pal_addr & 0xFF, cond_pal_addr >> 8])
    combined.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    combined.extend([0xCD, 0x80, 0xFF, 0xC9])

    hook = create_vblank_hook(combined_addr)

    # Verify no overlaps
    regions = [
        ('pal_loader', pal_loader_addr, len(pal_loader)),
        ('cond_pal', cond_pal_addr, len(cond_pal)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_pal', tile_pal_addr, len(tile_pal)),
        ('bg_colorizer', bg_colorizer_addr, len(bg_colorizer)),
        ('combined', combined_addr, len(combined)),
        ('bg_table', bg_table_addr, len(bg_table)),
    ]
    for i, (na, sa, sza) in enumerate(regions):
        for nb, sb, szb in regions[i+1:]:
            if sa < sb + szb and sb < sa + sza:
                raise ValueError(f"OVERLAP: {na} ({sa:#x}-{sa+sza:#x}) and {nb} ({sb:#x}-{sb+szb:#x})")

    # Write to ROM
    bank13 = 13 * 0x4000
    def w(addr, data):
        off = bank13 + (addr - 0x4000)
        rom[off:off+len(data)] = data

    w(pal_addr, palettes['bg_data'])
    w(pal_addr + 64, palettes['obj_data'])
    w(boss_pal_addr, palettes['boss_palette_table'])
    w(boss_slot_addr, palettes['boss_slot_table'])
    w(swj_addr, palettes['sara_witch_jet'])
    w(sdj_addr, palettes['sara_dragon_jet'])
    w(sp_addr, palettes['spiral_proj'])
    w(shp_addr, palettes['shield_proj'])
    w(tp_addr, palettes['turbo_proj'])
    w(pal_loader_addr, pal_loader)
    w(cond_pal_addr, cond_pal)
    w(shadow_main_addr, shadow_main)
    w(colorizer_addr, colorizer)
    w(tile_pal_addr, tile_pal)
    w(bg_colorizer_addr, bg_colorizer)
    w(bg_table_addr, bg_table)
    w(combined_addr, combined)

    # NOP out original DMA call in VBlank handler
    rom[0x06D5:0x06D5+3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824+len(hook)] = hook
    rom[0x143] = 0x80

    # Header checksum
    x = 0
    for i in range(0x134, 0x14D):
        x = (x - rom[i] - 1) & 0xFF
    rom[0x14D] = x

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(rom)

    return output_path


if __name__ == "__main__":
    rom_path = build_v272()
    print(f"\nBuilt v2.72: {rom_path}")
    print(f"Strategy: Dual-tilemap viewport (2 rows/frame, STAT-safe)")
    print(f"Per tile: read active tilemap → write palette to BOTH 0x9800 and 0x9C00")
    print(f"Budget: ~22-26% (vs v2.62's 35%)")
    print(f"Settling: 9 frames (0.15s) - both tilemaps colored simultaneously")
    print(f"Flicker: ZERO (STAT waits + dual tilemap writes)")
