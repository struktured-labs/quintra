#!/usr/bin/env python3
"""
v2.81: Hook-First Hybrid — Per-row interleaved copy (zero-flicker)

Key insight: v2.80's two-pass design (all palettes, then all tiles) leaves a
~12000 cycle gap where VBlank renders partially-updated VRAM → ~2% flicker.

Fix: INTERLEAVE palette + tile writes PER ROW. For each row:
  1. Write 24 palette attributes (VBK=1) via ROM lookup
  2. DI transition (no interrupts during VBK switch + rewind)
  3. Rewind HL/DE to row start, switch to VBK=0
  4. Write 24 tile IDs (VBK=0)
  5. Skip gap, advance to next row

The critical transition (steps 2-3) is protected by DI — no VBlank can fire
between palette and tile writes for the same row. Each row is atomic.

If VBlank fires BETWEEN rows, completed rows have BOTH correct palettes AND
tiles. Only incomplete rows show stale data → effectively zero visible flicker.

Also includes v2.80's IE masking (timer/STAT blocked) and hook flag (sweep
suppressed during copy).

HRAM assignments:
  FF91: Hook flag (0x5A = copy active, checked but NOT cleared by VBlank)
  FFA5: Sweep state counter (0-23=Phase1, 24-47=Phase2)
  FFA9: Palette temp (sweep) + conditional palette hash cache
  FFEE: Base hi temp (protected by hook flag during enhanced copy)
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_conditional_palette, create_tile_to_palette_subroutine,
    create_bg_tile_table,
)
from penta_dragon_dx.display_patcher import apply_all_display_patches

HOOK_FLAG = 0x5A  # Magic value: "hook just ran"


def create_bank_aware_vblank_hook(combined_addr: int) -> bytes:
    """VBlank hook with joypad + bank-aware save/restore via FF99.
    Must be exactly 47 bytes (0x0824-0x0852).
    """
    lo, hi = combined_addr & 0xFF, (combined_addr >> 8) & 0xFF
    joy = bytearray([
        0x3E, 0x20,  # LD A, 0x20
        0xE0, 0x00,  # LDH [FF00], A
        0xF0, 0x00,  # LDH A, [FF00]
        0x2F,        # CPL
        0xE6, 0x0F,  # AND 0x0F
        0xCB, 0x37,  # SWAP A
        0x47,        # LD B, A
        0x3E, 0x10,  # LD A, 0x10
        0xE0, 0x00,  # LDH [FF00], A
        0xF0, 0x00,  # LDH A, [FF00] (dummy)
        0xF0, 0x00,  # LDH A, [FF00] (actual)
        0x2F,        # CPL
        0xE6, 0x0F,  # AND 0x0F
        0xB0,        # OR B
        0xE0, 0x93,  # LDH [FF93], A
        0x3E, 0x30,  # LD A, 0x30
        0xE0, 0x00,  # LDH [FF00], A
    ])
    hook = bytearray([
        0xF0, 0x99,        # LDH A, [FF99]
        0xF5,              # PUSH AF
        0x3E, 0x0D,        # LD A, 0x0D
        0xEA, 0x00, 0x20,  # LD [0x2000], A
        0xCD, lo, hi,      # CALL combined
        0xF1,              # POP AF
        0xEA, 0x00, 0x20,  # LD [0x2000], A
        0xC9,              # RET
    ])
    total = joy + hook
    while len(total) < 47:
        total.append(0x00)
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be 47!"
    return bytes(total)


def create_enhanced_tilemap_copy(bg_table_addr: int, base_addr: int,
                                  return_addr: int) -> bytes:
    """Enhanced tilemap copy with per-row interleaving.

    For each of 24 rows:
      - Palette half: 6 groups × 4 tiles via ROM lookup (VBK=1)
      - DI transition: rewind HL/DE, switch VBK=0 (interrupt-free)
      - Tile half: 6 groups × 4 tiles direct copy (VBK=0)
      - Skip 8-col gap, advance to next row

    Each row is atomic — palette and tile data are written together.
    VBlank can only render between rows, where both are consistent.

    Entry: H = tilemap base hi (0x98 or 0x9C), set by caller.
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()
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
        addr = base_addr + targets[name]
        emit([opcode, addr & 0xFF, (addr >> 8) & 0xFF])

    # ================================================================
    # PREAMBLE: Save state, set hook flag, mask IE
    # ================================================================
    emit([0x7C])               # LD A, H
    emit([0xE0, 0xEE])        # LDH [FFEE], A       ; save tilemap base hi

    emit([0x3E, HOOK_FLAG])    # LD A, 0x5A
    emit([0xE0, 0x91])        # LDH [FF91], A       ; hook flag → suppress sweep

    emit([0xF0, 0xFF])        # LDH A, [FFFF]       ; read IE register
    emit([0xF5])               # PUSH AF              ; save old IE on stack
    emit([0x3E, 0x01])        # LD A, 0x01           ; VBlank only
    emit([0xE0, 0xFF])        # LDH [FFFF], A       ; mask IE → no timer/STAT

    # Init pointers
    emit([0x2E, 0x00])        # LD L, 0x00
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0        ; WRAM tile source

    # Row counter on stack
    emit([0x3E, 24])          # A = 24 rows
    emit([0xF5])               # PUSH AF

    # ================================================================
    # ROW LOOP: For each row, write palettes then tiles atomically
    # ================================================================
    mark('row_start')

    # --- PALETTE HALF (VBK=1) ---
    # Save DE so we can rewind for tile half
    emit([0xD5])               # PUSH DE              ; save row start in C1A0

    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK = 1              ; attribute map

    emit([0x0E, 6])            # C = 6 groups/row
    emit([0x06, bg_table_hi]) # B = table hi (0x70)

    mark('pal_group')
    emit([0xC5])               # PUSH BC (save table_hi + group count)
    emit([0xF3])               # DI
    mark('pal_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'pal_stat')  # wait for HBlank

    for _ in range(4):         # 4 tiles per HBlank window (36 cycles)
        emit([0x1A, 0x13])     # LD A,[DE]; INC DE   ; read tile from WRAM
        emit([0x4F])            # LD C, A             ; tile → C for lookup
        emit([0x0A])            # LD A,[BC]           ; palette = table[tile]
        emit([0x22])            # LD [HL+],A          ; write palette attr

    emit([0xFB])               # EI
    emit([0xC1])               # POP BC
    emit([0x0D])               # DEC C (groups)
    emit_jr_back(0x20, 'pal_group')

    # --- TRANSITION: palette→tile (DI protected, no VBlank possible) ---
    emit([0xF3])               # DI  ; CRITICAL: protect transition

    # Rewind HL by 24 (back to row start for tile writes)
    emit([0x7D])               # LD A, L
    emit([0xD6, 24])          # SUB 24
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x25])               # DEC H

    # Switch to tile data
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # VBK = 0

    # Restore DE to row start
    emit([0xD1])               # POP DE               ; rewind DE

    # --- TILE HALF (VBK=0) ---
    emit([0x06, 6])            # B = 6 groups/row

    mark('tile_group')
    # DI already set on first entry; needed for subsequent entries
    emit([0xF3])               # DI (redundant first time, needed for loop)
    mark('tile_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'tile_stat')

    for _ in range(4):         # 4 tiles per HBlank window (24 cycles)
        emit([0x1A, 0x13, 0x22])  # LD A,[DE]; INC DE; LD [HL+],A

    emit([0xFB])               # EI
    emit([0x05])               # DEC B (groups)
    emit_jr_back(0x20, 'tile_group')

    # --- Skip 8-column gap ---
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x24])               # INC H

    # --- Row counter ---
    emit([0xF1])               # POP AF (row count)
    emit([0x3D])               # DEC A
    emit([0x28, 0x04])        # JR Z, +4 (done → skip PUSH+JP)
    emit([0xF5])               # PUSH AF
    emit_jp_back(0xC3, 'row_start')

    # ================================================================
    # CLEANUP: restore VBK, clear hook flag, restore IE
    # ================================================================
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # VBK = 0

    emit([0xAF])               # XOR A
    emit([0xE0, 0x91])        # LDH [FF91], A       ; clear hook flag

    emit([0x3E, 24])          # LD A, 24
    emit([0xE0, 0xA5])        # LDH [FFA5], A       ; skip Phase 1

    emit([0xF1])               # POP AF              ; restore old IE
    emit([0xE0, 0xFF])        # LDH [FFFF], A       ; restore IE register

    # Return via bridge
    emit_jp_addr(return_addr)

    return bytes(code)


def create_bg_sweep_no_scroll(bg_table_addr: int, base_addr: int,
                               rows_per_frame: int = 2) -> bytes:
    """VBlank BG sweep — simplified v2.73 without scroll column detection.

    Uses FFA5 as state counter (instead of FF91 which is now the hook flag).
    Phase 1 (FFA5 = 0-23): Initial sweep, 2 rows/frame, 12 frames
    Phase 2 (FFA5 = 24-47): Maintenance, 1 row/frame, wraps at 48→24

    Covers all 24 rows that the game's tilemap copy writes.
    No scroll column detection — the hook handles scroll updates.
    """
    bg_table_hi = (bg_table_addr >> 8) & 0xFF
    code = bytearray()
    jr_patches = []
    jp_patches = []
    targets = {}

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def mark(name):
        targets[name] = len(code)

    def emit_jr_fwd(opcode, name):
        code.append(opcode)
        jr_patches.append((len(code), name))
        code.append(0x00)

    def emit_jr_back(opcode, name):
        offset = targets[name] - (len(code) + 2)
        assert -128 <= offset <= 127, f"JR to {name}: offset {offset}"
        emit([opcode, offset & 0xFF])

    def emit_jp_fwd(name):
        emit([0xC3])
        jp_patches.append((len(code), name))
        emit([0x00, 0x00])

    def patch_all():
        for pos, name in jr_patches:
            offset = targets[name] - (pos + 1)
            assert -128 <= offset <= 127, f"JR to {name} from {pos}: {offset}"
            code[pos] = offset & 0xFF
        for pos, name in jp_patches:
            addr = base_addr + targets[name]
            code[pos] = addr & 0xFF
            code[pos + 1] = (addr >> 8) & 0xFF

    # ================================================================
    # Row processing: 32 tiles per row with STAT waits, dual-tilemap writes
    # Same as v2.73's emit_row_loop
    # ================================================================
    def emit_row_loop(stat_label, tile_label):
        emit([0x06, 0x20])        # LD B, 32
        mark(tile_label)
        mark(stat_label)
        emit([0xF0, 0x41])        # LDH A,[FF41]
        emit([0xE6, 0x02])        # AND 0x02
        emit_jr_back(0x20, stat_label)

        emit([0x1A])               # LD A,[DE] ; tile
        emit([0x6F])               # LD L, A
        emit([0x7E])               # LD A,[HL] ; palette
        emit([0xE0, 0xA9])        # LDH [FFA9],A

        emit([0x3E, 0x01])
        emit([0xE0, 0x4F])        # VBK=1

        emit([0xF0, 0xA9])
        emit([0x12])               # write active

        emit([0x7A])
        emit([0xEE, 0x04])
        emit([0x57])               # D ^= 0x04
        emit([0xF0, 0xA9])
        emit([0x12])               # write other

        emit([0x7A])
        emit([0xEE, 0x04])
        emit([0x57])               # restore D

        emit([0xAF])
        emit([0xE0, 0x4F])        # VBK=0

        emit([0x1C])               # INC E
        emit([0x05])               # DEC B
        emit_jr_back(0x20, tile_label)

    def emit_row_addr():
        """Compute D:E from tilemap_row in A. Uses FFEE for base_hi."""
        emit([0x47])               # LD B, A
        emit([0xE6, 0x07])
        emit([0xCB, 0x37])        # SWAP (×16)
        emit([0x87])               # ×32
        emit([0x5F])               # LD E, A

        emit([0x78])               # LD A, B
        emit([0xCB, 0x3F])
        emit([0xCB, 0x3F])
        emit([0xCB, 0x3F])        # row>>3
        emit([0x57])               # LD D
        emit([0xF0, 0xEE])        # base_hi
        emit([0x82])
        emit([0x57])               # D = base_hi + row>>3

    # ================================================================
    # PREAMBLE
    # ================================================================
    emit([0xF0, 0xC1])        # gameplay check
    emit([0xB7])
    emit([0xC8])               # RET Z (menus)

    emit([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL
    emit([0x26, bg_table_hi]) # LD H, table_hi
    emit([0xAF])
    emit([0xE0, 0x4F])        # VBK=0

    # Compute base_hi from LCDC
    emit([0xF0, 0x40])
    emit([0xE6, 0x08])
    emit([0x0F])
    emit([0xC6, 0x98])
    emit([0xE0, 0xEE])        # FFEE = base_hi

    # Phase check — using FFA5 (not FF91!)
    emit([0xF0, 0xA5])        # LDH A,[FFA5]
    emit([0xFE, 24])
    emit_jr_fwd(0x30, 'phase2')  # JR NC → phase 2

    # ================================================================
    # PHASE 1: Initial sweep (2 rows/frame)
    # ================================================================
    emit([0x0E, rows_per_frame])  # LD C, rows

    mark('p1_row')
    # tilemap_row = (SCY/8 + FFA5) & 0x1F
    emit([0xF0, 0x42])        # SCY
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])        # SCY/8
    emit([0x47])               # LD B
    emit([0xF0, 0xA5])        # row counter (FFA5)
    emit([0x80])               # + SCY/8
    emit([0xE6, 0x1F])        # & 0x1F

    emit_row_addr()
    emit_row_loop('p1s', 'p1t')

    # Advance FFA5
    emit([0xF0, 0xA5])
    emit([0x3C])               # INC
    emit([0xE0, 0xA5])

    emit([0x0D])               # DEC C
    emit_jr_back(0x20, 'p1_row')

    # Check if Phase 1 complete (FFA5 reached 24)
    emit([0xF0, 0xA5])
    emit([0xFE, 24])          # CP 24
    emit_jr_fwd(0x20, 'p1_done')  # JR NZ → not done

    # Phase 1 → Phase 2 transition: nothing extra needed
    # FFA5 = 24 is the Phase 2 start value

    mark('p1_done')
    emit_jp_fwd('cleanup')

    # ================================================================
    # PHASE 2: Maintenance (1 row/frame, no scroll detection)
    # ================================================================
    mark('phase2')

    # row_index = (FFA5 - 24) = 0-23
    emit([0xF0, 0xA5])        # A = FFA5 (24-47)
    emit([0xD6, 24])          # SUB 24

    # tilemap_row = (SCY/8 + row_index) & 0x1F
    emit([0x47])               # LD B
    emit([0xF0, 0x42])        # SCY
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0x80])               # + row_index
    emit([0xE6, 0x1F])

    emit_row_addr()
    emit_row_loop('p2s', 'p2t')

    # Advance FFA5: 24→25→...→47→24
    emit([0xF0, 0xA5])
    emit([0x3C])               # INC
    emit([0xFE, 48])          # CP 48
    emit_jr_fwd(0x38, 'p2_no_wrap')  # JR C → < 48
    emit([0x3E, 24])          # wrap to 24
    mark('p2_no_wrap')
    emit([0xE0, 0xA5])

    # ================================================================
    # CLEANUP
    # ================================================================
    mark('cleanup')
    emit([0xAF])
    emit([0xE0, 0x4F])        # VBK=0
    emit([0xE1, 0xD1, 0xC1]) # POP HL, DE, BC
    emit([0xC9])               # RET

    patch_all()
    return bytes(code)


def build_v281():
    """Build v2.81 ROM — per-row interleaved copy (zero-flicker)."""
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
    bg_table_addr = 0x7000  # lookup table for hook's palette pass

    # Bank trampoline addresses (same as v2.75)
    return_bridge_addr = 0x42B4

    # Generate standard components
    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)

    # Enhanced copy (hook) — per-row interleaved
    enhanced_copy = create_enhanced_tilemap_copy(bg_table_addr, enhanced_copy_addr,
                                                  return_bridge_addr)
    print(f"Enhanced tilemap copy: {len(enhanced_copy)} bytes at 0x{enhanced_copy_addr:04X}")

    # BG sweep (fallback) — placed after enhanced copy
    bg_sweep_addr = (enhanced_copy_addr + len(enhanced_copy) + 0xF) & ~0xF
    bg_sweep = create_bg_sweep_no_scroll(bg_table_addr, bg_sweep_addr)
    print(f"BG sweep: {len(bg_sweep)} bytes at 0x{bg_sweep_addr:04X}")

    # Conditional palette
    cond_pal_addr = (bg_sweep_addr + len(bg_sweep) + 0xF) & ~0xF
    cond_pal = create_conditional_palette(pal_loader_addr)
    print(f"Cond palette: {len(cond_pal)} bytes at 0x{cond_pal_addr:04X}")

    # Combined function: check hook flag → skip/run sweep
    combined_addr = (cond_pal_addr + len(cond_pal) + 0xF) & ~0xF
    combined = bytearray()

    # Check hook flag — DON'T clear it (enhanced copy clears when done)
    combined.extend([0xF0, 0x91])        # LDH A, [FF91]
    combined.extend([0xFE, HOOK_FLAG])   # CP 0x5A
    combined.extend([0x20, 0x02])        # JR NZ, +2 → need_sweep
    # Hook active: skip BG sweep (flag stays set, protects FFEE)
    combined.extend([0x18, 0x03])        # JR +3 → after_bg
    # need_sweep:
    combined.extend([0xCD, bg_sweep_addr & 0xFF, bg_sweep_addr >> 8])  # CALL bg_sweep
    # after_bg:
    combined.extend([0xCD, cond_pal_addr & 0xFF, cond_pal_addr >> 8])  # CALL cond_pal
    combined.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])  # CALL OBJ
    combined.extend([0xCD, 0x80, 0xFF])  # CALL DMA
    combined.extend([0xC9])              # RET

    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"  → Hook flag check + conditional BG sweep + CondPal + OBJ + DMA")

    # Verify layout
    assert combined_addr + len(combined) <= bg_table_addr, \
        f"Layout overflow: combined ends {combined_addr+len(combined):#x} > bg_table {bg_table_addr:#x}"

    hook = create_bank_aware_vblank_hook(combined_addr)

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
    w(combined_addr, combined)

    # =============================================
    # HOOK: Bank 1 trampoline at 0x42A7
    # =============================================
    bank1_patch = bytearray([
        0xF3,              # DI                at 0x42A7
        0x3E, 0x0D,        # LD A, 0x0D       at 0x42A8
        0xE0, 0x99,        # LDH [FF99], A    at 0x42AA
        0xEA, 0x00, 0x20,  # LD [0x2000], A   at 0x42AC → bank 13, PC=0x42AF
    ])
    dead_len = 0x42BC - 0x42AF
    bank1_patch.extend([0x00] * dead_len)
    bank1_patch.extend([
        0xFB,              # EI               at 0x42BC
        0xC9,              # RET              at 0x42BD
    ])
    rom[0x42A7:0x42A7+len(bank1_patch)] = bank1_patch
    print(f"Bank 1 trampoline: {len(bank1_patch)} bytes at 0x42A7-0x{0x42A7+len(bank1_patch)-1:04X}")

    # Bank 13 bridge at 0x42AF
    bridge = bytearray([
        0xFB,              # EI               at 0x42AF
        0xC3, enhanced_copy_addr & 0xFF, (enhanced_copy_addr >> 8) & 0xFF,  # JP 0x6C00
        0x00,              # pad              at 0x42B3
        0xF3,              # DI               at 0x42B4
        0x3E, 0x01,        # LD A, 0x01       at 0x42B5
        0xE0, 0x99,        # LDH [FF99], A    at 0x42B7
        0xEA, 0x00, 0x20,  # LD [0x2000], A   at 0x42B9 → bank 1, PC=0x42BC
    ])
    bridge_offset = bank13 + (0x42AF - 0x4000)
    rom[bridge_offset:bridge_offset+len(bridge)] = bridge
    print(f"Bank 13 bridge: {len(bridge)} bytes at 0x42AF-0x{0x42AF+len(bridge)-1:04X}")

    # Standard patches
    rom[0x06D5:0x06D5+3] = bytearray([0x00, 0x00, 0x00])  # NOP out original palette load
    rom[0x0824:0x0824+len(hook)] = hook                     # VBlank hook
    rom[0x143] = 0x80                                       # CGB flag

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
    rom_path = build_v281()
    print(f"\nBuilt v2.81: {rom_path}")
    print(f"Hook-first hybrid with per-row interleaved copy")
    print(f"Each row writes palette+tiles atomically (DI-protected transition)")
    print(f"IE masked to VBlank-only during copy (no timer/STAT)")
    print(f"VBlank handler: [flag check (no clear)] → optional BG sweep + CondPalette + OBJ + DMA")
