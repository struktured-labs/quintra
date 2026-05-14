#!/usr/bin/env python3
"""
v2.74: O(1) Tilemap Hook + v2.73 Maintenance Sweep

Two-pronged BG colorization:
  1. HOOK at 0x42A7: Intercepts game's bulk tilemap copy (level loading).
     Enhanced copy writes palette attributes alongside tiles. Runs during
     game's main loop — zero VBlank cost. Sets FF91=18 to skip Phase 1.
  2. v2.73 sweep (VBlank): Phase 1 for save states, Phase 2 for maintenance.
     Handles ongoing tile changes from gameplay (enemy spawns, items, etc.)

Improvement over v2.73:
  - Level loads: instant BG coloring (hook), no 9-frame Phase 1 settle
  - Save states: Phase 1 still runs (9 frames), then Phase 2 maintenance
  - Phase 2 steady state: same as v2.73 (~13% stationary, ~18% scrolling)

Flow (hook):
  Caller → 0x42A7 (bank 1: switch to bank 13)
         → 0x42AC (bank 13: JP 0x6C00)
         → 0x6C00 (enhanced copy: tiles + palettes)
         → JP 0x42B0 (bank 13: switch to bank 1)
         → 0x42B5 (bank 1: RET)
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
from create_vblank_colorizer_v273 import create_bg_colorizer_scroll_triggered
from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_enhanced_tilemap_copy(bg_table_addr: int, base_addr: int,
                                  return_addr: int) -> bytes:
    """Enhanced tilemap copy: Pass 1 (tiles) + Pass 2 (palette attributes).

    Simple 2-pass design using STAT-wait per tile. No DI/EI (caller provides DI).
    Pass 1: Copy tiles from C1A0 to VRAM (24 cols × 24 rows).
    Pass 2: Lookup palette from ROM table, write to VRAM attributes (VBK=1).

    Entry: H = tilemap base hi (0x98 or 0x9C), set by caller. DI already active.
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()
    jp_patches = []
    targets = {}

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def mark(name):
        targets[name] = len(code)

    def emit_jr_back(opcode, name):
        offset = targets[name] - (len(code) + 2)
        assert -128 <= offset <= 127, f"JR to {name}: offset {offset}"
        emit([opcode, offset & 0xFF])

    def emit_jp_addr(addr):
        emit([0xC3, addr & 0xFF, (addr >> 8) & 0xFF])

    def emit_jp_back(opcode, name):
        """Emit conditional or unconditional JP to a backward target."""
        addr = base_addr + targets[name]
        emit([opcode, addr & 0xFF, (addr >> 8) & 0xFF])

    def patch_all():
        for pos, name in jp_patches:
            addr = base_addr + targets[name]
            code[pos] = addr & 0xFF
            code[pos + 1] = (addr >> 8) & 0xFF

    def emit_jp_fwd(opcode, name):
        """Emit JP with forward patch. opcode: 0xC3=JP, 0xCA=JP Z, 0xC2=JP NZ"""
        emit([opcode])
        jp_patches.append((len(code), name))
        emit([0x00, 0x00])

    # Save H to HRAM (needed by Pass 2 to rewind HL)
    emit([0x7C])               # LD A, H
    emit([0xE0, 0xEE])        # LDH [FFEE], A  ; save base_hi

    # ================================================================
    # PASS 1: Tile copy from C1A0 to VRAM (24 cols × 24 rows)
    # Simple loop: STAT wait → copy 1 tile, repeat 24 cols, skip 8 gap
    # ================================================================
    emit([0x2E, 0x00])        # LD L, 0x00  ; HL = tilemap base
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0
    emit([0x0E, 24])          # C = 24 rows

    mark('p1_row')
    emit([0x06, 24])           # B = 24 cols

    mark('p1_tile')
    mark('p1_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'p1_stat')  # JR NZ (wait for HBlank/VBlank)

    emit([0x1A, 0x13])        # LD A,[DE]; INC DE  ; read tile from WRAM
    emit([0x22])               # LD [HL+],A         ; write to VRAM

    emit([0x05])               # DEC B
    emit_jr_back(0x20, 'p1_tile')  # JR NZ

    # Skip 8-column gap: L += 8
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x24])               # INC H

    emit([0x0D])               # DEC C (row counter)
    emit_jp_back(0xC2, 'p1_row')  # JP NZ, p1_row

    # ================================================================
    # PASS 2: Palette attributes via ROM lookup (VBK=1)
    # Register plan: HL=VRAM write, DE=C1A0 read, B=table_hi, C=tile_id(temp)
    # Row counter in FFA9, col counter on stack via PUSH/POP BC
    # ================================================================
    emit([0xF0, 0xEE])
    emit([0x67])               # H = base_hi
    emit([0x2E, 0x00])        # L = 0
    emit([0x11, 0xA0, 0xC1]) # DE = C1A0

    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK=1

    emit([0x3E, 24])
    emit([0xE0, 0xA9])        # FFA9 = 24 rows

    mark('p2_row')
    # Use stack to hold col counter: push 24, use B for table hi
    emit([0x01, 24, bg_table_hi])  # LD BC, cols|table_hi  (C=24, B=table_hi)
    emit([0xC5])                    # PUSH BC

    mark('p2_tile')
    mark('p2_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'p2_stat')  # JR NZ

    emit([0x1A, 0x13])        # LD A,[DE]; INC DE  ; read tile from WRAM
    emit([0x4F])               # LD C, A            ; C = tile_id
    emit([0x0A])               # LD A,[BC]          ; palette = table[tile_id]
    emit([0x22])               # LD [HL+],A         ; write palette attr

    # Decrement col counter on stack
    # POP BC → DEC C → check → PUSH BC → restore B
    # On SM83: POP, DEC, PUSH, LD don't affect flags from DEC
    emit([0xC1])               # POP BC (B=table_hi, C=col_counter)
    emit([0x0D])               # DEC C
    emit([0xC5])               # PUSH BC (save, flags preserved)
    emit_jr_back(0x20, 'p2_tile')  # JR NZ → more cols

    emit([0xC1])               # POP BC (cleanup)

    # Skip 8-column gap
    emit([0x7D])
    emit([0xC6, 0x08])
    emit([0x6F])
    emit([0x30, 0x01])
    emit([0x24])

    emit([0xF0, 0xA9])
    emit([0x3D])               # DEC A (rows)
    emit([0xE0, 0xA9])
    emit_jp_back(0xC2, 'p2_row')  # JP NZ, p2_row

    # VBK=0
    emit([0xAF])
    emit([0xE0, 0x4F])

    # Return
    emit_jp_addr(return_addr)

    patch_all()
    return bytes(code)


def build_v274():
    """Build v2.74 ROM."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)
    palettes = load_palettes_from_yaml(palette_yaml)

    # Address layout
    pal_addr = 0x6800
    boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0

    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    enhanced_copy_addr = 0x6C00
    bg_table_addr = 0x7000  # lookup table for hook's Pass 2

    # DI at 0x42A7 shifts bank switch by 1 byte: bank 13 bridge at 0x42AD
    # Return path: bank 13 at 0x42B1 → switch to bank 1 → bank 1 at 0x42B6 (EI; RET)
    return_bridge_addr = 0x42B1

    # Generate shared components
    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)

    # Enhanced copy (hook)
    enhanced_copy = create_enhanced_tilemap_copy(bg_table_addr, enhanced_copy_addr,
                                                  return_bridge_addr)
    print(f"Enhanced tilemap copy: {len(enhanced_copy)} bytes at 0x{enhanced_copy_addr:04X}")

    # VBlank BG sweep (reuse v2.73's proven implementation)
    # BG table for sweep uses a DIFFERENT address (0x7000 range)
    sweep_bg_table_addr = 0x7100
    sweep_bg_table = create_bg_tile_table(ff_filter=False)

    bg_sweep_addr = (enhanced_copy_addr + len(enhanced_copy) + 0xF) & ~0xF
    bg_sweep = create_bg_colorizer_scroll_triggered(sweep_bg_table_addr, bg_sweep_addr)
    print(f"BG sweep (v2.73): {len(bg_sweep)} bytes at 0x{bg_sweep_addr:04X}")

    cond_pal_addr = (bg_sweep_addr + len(bg_sweep) + 0xF) & ~0xF
    cond_pal = create_conditional_palette(pal_loader_addr)
    print(f"Cond palette: {len(cond_pal)} bytes at 0x{cond_pal_addr:04X}")

    combined_addr = (cond_pal_addr + len(cond_pal) + 0xF) & ~0xF

    # Combined: BG_sweep → CondPalette → OBJ → DMA
    combined = bytearray()
    combined.extend([0xCD, bg_sweep_addr & 0xFF, bg_sweep_addr >> 8])
    combined.extend([0xCD, cond_pal_addr & 0xFF, cond_pal_addr >> 8])
    combined.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    combined.extend([0xCD, 0x80, 0xFF, 0xC9])
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Verify layout fits
    assert combined_addr + len(combined) <= bg_table_addr, \
        f"Layout overflow: combined ends {combined_addr+len(combined):#x} > bg_table {bg_table_addr:#x}"
    assert sweep_bg_table_addr + 256 <= 0x8000, \
        f"Sweep BG table overflow at {sweep_bg_table_addr:#x}"

    hook = create_vblank_hook(combined_addr)

    # Overlap check
    regions = [
        ('pal_loader', pal_loader_addr, len(pal_loader)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_pal', tile_pal_addr, len(tile_pal)),
        ('enhanced_copy', enhanced_copy_addr, len(enhanced_copy)),
        ('bg_sweep', bg_sweep_addr, len(bg_sweep)),
        ('cond_pal', cond_pal_addr, len(cond_pal)),
        ('combined', combined_addr, len(combined)),
        ('bg_table', bg_table_addr, len(bg_table)),
        ('sweep_bg_table', sweep_bg_table_addr, len(sweep_bg_table)),
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
    w(enhanced_copy_addr, enhanced_copy)
    w(bg_sweep_addr, bg_sweep)
    w(bg_table_addr, bg_table)
    w(sweep_bg_table_addr, sweep_bg_table)
    w(combined_addr, combined)

    # Hook at 0x42A7: controlled by ENABLE_HOOK flag
    ENABLE_HOOK = True  # Tilemap copy hook for instant BG coloring

    if ENABLE_HOOK:
        # Bank 1 entry trampoline at 0x42A7 (with DI to prevent VBlank during bank 13)
        bank1_patch = bytearray([
            0xF3,              # DI
            0x3E, 0x0D,        # LD A, 0x0D  (bank 13)
            0xEA, 0x00, 0x20,  # LD [0x2000], A → bank 13 at 0x42AD
        ])
        bank1_patch.extend([0x00] * 9)   # dead zone 42AD-42B5
        bank1_patch.extend([0xFB, 0xC9]) # EI; RET at 42B6-42B7
        rom[0x42A7:0x42A7+len(bank1_patch)] = bank1_patch

        # Bank 13 bridge at 0x42AD
        bridge = bytearray([
            0xC3, enhanced_copy_addr & 0xFF, (enhanced_copy_addr >> 8) & 0xFF,
            0x00,
            0x3E, 0x01,
            0xEA, 0x00, 0x20,
        ])
        bridge_offset = bank13 + (0x42AD - 0x4000)
        rom[bridge_offset:bridge_offset+len(bridge)] = bridge

    # Standard patches
    rom[0x06D5:0x06D5+3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824+len(hook)] = hook
    rom[0x143] = 0x80

    x = 0
    for i in range(0x134, 0x14D):
        x = (x - rom[i] - 1) & 0xFF
    rom[0x14D] = x

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(rom)
    return output_path


if __name__ == "__main__":
    rom_path = build_v274()
    print(f"\nBuilt v2.74: {rom_path}")
    print(f"Hook: O(1) tilemap copy (instant BG on level load, 0% VBlank)")
    print(f"Sweep: v2.73 Phase 1+2 (save states + maintenance)")
    print(f"Phase 2 steady state: ~13% stationary, ~18% scrolling")
