#!/usr/bin/env python3
"""
v2.73: Scroll-triggered BG colorizer with maintenance sweep

Two-phase design:
  Phase 1 (FF91 < 18): Initial sweep - 2 rows/frame, dual-tilemap writes
    When row 18 reached → enter Phase 2

  Phase 2 (FF91 = 18-35): Scroll-triggered + 1 maintenance row/frame
    1. Always: color 1 maintenance row (32 tiles, cycles through rows 0-17)
    2. Check SCX/8: if changed, also color newly-revealed column (18 tiles)
    3. Large SCX jump → reset to Phase 1

Budget:
  Phase 1:    ~22% (64 tiles/frame, 9 frames settle) - same as v2.72
  Phase 2:    ~13% stationary (32 tiles/frame maintenance)
              ~18% scrolling (32 + 18 tiles/frame)
  vs v2.72:   ~26% always (64 tiles/frame)

Re-sweep period: 18 frames (0.3s) to refresh all visible tiles
This handles tile changes from game logic (enemies, items, animations)

HRAM: FF91=phase+row (0-17=sweep, 18-35=maintenance), FFA5=prev SCX/8
      FFA9=palette temp, FFEE=base_hi temp
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


def create_bg_colorizer_scroll_triggered(bg_table_addr: int, base_addr: int,
                                          rows_per_frame: int = 2) -> bytes:
    """Scroll-triggered BG colorizer with maintenance sweep.

    FF91 state machine:
      0-17:  Phase 1 - initial sweep, process `rows_per_frame` rows/frame
      18-35: Phase 2 - 1 maintenance row/frame (row = FF91-18) + scroll columns
      On reaching 36: wrap to 18
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
    # SHARED: Emit the tile-row processing subroutine as inline code
    # Inputs: D:E = row start addr, H = table hi, FFEE = base_hi
    # Processes 32 tiles with STAT waits and dual-tilemap writes
    # Clobbers: A, B, D (restored), L, FFA9
    # Preserves: C, E (wraps to E+32 = same low byte after 32 INC E)
    # ================================================================
    def emit_row_loop(stat_label, tile_label):
        """Emit 32-tile row processing loop. Returns nothing (inline)."""
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

    # ================================================================
    # SHARED: Compute row address in D:E from tilemap_row (in A)
    # Inputs: A = tilemap_row (0-31), FFEE = base_hi
    # Outputs: D:E = tilemap address of row start
    # Clobbers: A, B (temp)
    # ================================================================
    def emit_row_addr():
        emit([0x47])               # LD B, A ; save tilemap_row
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

    # Phase check
    emit([0xF0, 0x91])        # LDH A,[FF91]
    emit([0xFE, 18])
    emit_jr_fwd(0x30, 'phase2')  # JR NC → phase 2

    # ================================================================
    # PHASE 1: Initial sweep (2 rows/frame)
    # ================================================================
    emit([0x0E, rows_per_frame])  # LD C, rows

    mark('p1_row')
    # tilemap_row = (SCY/8 + FF91) & 0x1F
    emit([0xF0, 0x42])        # SCY
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])        # SCY/8
    emit([0x47])               # LD B
    emit([0xF0, 0x91])        # row counter
    emit([0x80])               # + SCY/8
    emit([0xE6, 0x1F])        # & 0x1F

    emit_row_addr()
    emit_row_loop('p1s', 'p1t')

    # Advance row counter
    emit([0xF0, 0x91])
    emit([0x3C])               # INC
    emit([0xE0, 0x91])        # save

    emit([0x0D])               # DEC C
    emit_jr_back(0x20, 'p1_row')

    # Check if we just finished all 18 rows
    emit([0xF0, 0x91])
    emit([0xFE, 18])
    emit_jp_fwd('cleanup')     # if < 18: not done yet, just exit
    # Actually, we need JR C to cleanup (if < 18). But cleanup is far.
    # Wait - if FF91 < 18 we should exit normally (more rows next frame).
    # If FF91 >= 18, we transition. But after incrementing, FF91 could be
    # 2 (from 0), 4 (from 2), etc. It won't be >=18 until the 9th call.
    # When it reaches 18, we're done with Phase 1.
    # The JP above always runs - we need to make it conditional.

    # Let me restructure: after the row loop, check if FF91 reached 18.
    # If not, cleanup. If yes, init FFA5 and cleanup (FF91=18 starts Phase 2).

    # Oops, the JP above is unconditional. Let me fix - I need the check
    # to happen BEFORE the JP. Let me move this.

    # Actually - when FF91 reaches 18, that's exactly the Phase 2 start value.
    # Phase 2 starts at FF91=18. So we just need to initialize FFA5 when
    # FF91 transitions from 17 to 18. Let me do that:
    # After incrementing FF91, if it equals 18, also set FFA5 = SCX/8.

    # But wait - I already emitted the JP cleanup. Let me back up.
    # The problem is that the code flow is: emit row loop → advance → DEC C → JR NZ p1_row → fall through.
    # After fall-through (C=0), we need to check if FF91 reached 18.

    # I emitted an unconditional JP to cleanup which is wrong. Let me restructure.
    # Remove the last JP and redo.

    # Actually I realize the code structure is wrong. Let me remove the bad JP
    # and add the transition check properly.

    # The emit_jp_fwd('cleanup') is the last thing emitted. Remove it:
    del jp_patches[-1]
    code[:] = code[:-3]  # remove the 3 bytes (C3 xx xx)

    # Now: after DEC C / JR NZ p1_row falls through when C=0.
    # Check if FF91 reached 18 → need to init FFA5
    emit([0xF0, 0x91])
    emit([0xFE, 18])
    emit_jr_fwd(0x20, 'p1_init_scroll')  # JR NZ → FF91 != 18, skip init
    # Note: this is wrong - we want JR Z (if FF91 == 18, do init).
    # CP 18; JR Z means Z flag is set when A==18. But JR Z is 0x28.

    # Fix: use JR NZ to skip over the init code
    # Remove wrong JR
    del jr_patches[-1]
    code[:] = code[:-2]

    emit([0xF0, 0x91])
    emit([0xFE, 18])          # CP 18
    emit_jr_fwd(0x20, 'p1_done')  # JR NZ → not 18 yet, skip init

    # FF91 just reached 18 → initialize scroll baseline
    emit([0xF0, 0x43])        # SCX
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xE0, 0xA5])        # FFA5 = SCX/8

    mark('p1_done')
    emit_jp_fwd('cleanup')

    # ================================================================
    # PHASE 2: Maintenance row + scroll-triggered column
    # ================================================================
    mark('phase2')

    # --- Part A: Maintenance row ---
    # row_index = (FF91 - 18) = 0-17
    emit([0xF0, 0x91])        # A = FF91 (18-35)
    emit([0xD6, 18])          # SUB 18 → row_index 0-17

    # tilemap_row = (SCY/8 + row_index) & 0x1F
    emit([0x47])               # LD B, row_index
    emit([0xF0, 0x42])        # SCY
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0x80])               # + row_index
    emit([0xE6, 0x1F])

    emit_row_addr()
    emit_row_loop('p2s', 'p2t')

    # Advance FF91: 18→19→...→35→18
    emit([0xF0, 0x91])
    emit([0x3C])               # INC
    emit([0xFE, 36])          # CP 36
    emit_jr_fwd(0x38, 'p2_no_wrap')  # JR C → < 36
    emit([0x3E, 18])          # wrap to 18
    mark('p2_no_wrap')
    emit([0xE0, 0x91])

    # --- Part B: Scroll check ---
    emit([0xF0, 0x43])        # SCX
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])        # new_scx8
    emit([0x47])               # LD B

    emit([0xF0, 0xA5])        # prev_scx8
    emit([0xB8])               # CP B
    emit_jp_fwd('cleanup')     # JP Z → no scroll (unconditional JP, but we need conditional)

    # Oops, JP doesn't have a Z variant in this form. JP cc,nn:
    # JP Z,nn = 0xCA nn nn
    # Let me fix:
    del jp_patches[-1]
    code[:] = code[:-3]

    # JP Z, cleanup
    emit([0xCA])               # JP Z, nn
    jp_patches.append((len(code), 'cleanup'))
    emit([0x00, 0x00])

    # Scroll detected
    emit([0x4F])               # C = prev_scx8
    emit([0x78])               # A = new_scx8
    emit([0x91])               # SUB → delta

    # Range check
    emit([0xFE, 0x11])
    emit_jr_fwd(0x38, 'right')
    emit([0xFE, 0xF0])
    emit_jr_fwd(0x30, 'left')

    # Big jump → reset to Phase 1
    emit([0xAF])
    emit([0xE0, 0x91])        # FF91 = 0
    emit_jp_fwd('cleanup')

    mark('right')
    emit([0x78])               # new_scx8
    emit([0xC6, 19])          # + 19 (right edge)
    emit([0xE6, 0x1F])
    emit_jr_fwd(0x18, 'col_ready')

    mark('left')
    emit([0x78])               # new_scx8
    emit([0xE6, 0x1F])

    mark('col_ready')
    emit([0x4F])               # C = column

    # Update FFA5
    emit([0x78])
    emit([0xE0, 0xA5])

    # Column loop: 18 rows
    emit([0x06, 18])          # B = 18

    mark('p2_col_row')
    emit([0xC5])               # PUSH BC

    # row_offset = 18 - B
    emit([0x3E, 18])
    emit([0x90])
    emit([0x47])               # B = offset

    # tilemap_row = (SCY/8 + offset) & 0x1F
    emit([0xF0, 0x42])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0x80])
    emit([0xE6, 0x1F])

    # addr: lo = (row&7)*32 + col, hi = base + (row>>3)
    emit([0x47])               # B = tilemap_row
    emit([0xE6, 0x07])
    emit([0xCB, 0x37])
    emit([0x87])
    emit([0x81])               # + C (column)
    emit([0x5F])               # E

    emit([0x78])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0xCB, 0x3F])
    emit([0x57])               # D
    emit([0xF0, 0xEE])
    emit([0x82])
    emit([0x57])

    # STAT wait + tile read + dual write (single tile)
    mark('p2cs')
    emit([0xF0, 0x41])
    emit([0xE6, 0x02])
    emit_jr_back(0x20, 'p2cs')

    emit([0x1A])               # tile
    emit([0x6F])
    emit([0x7E])               # palette

    emit([0xE0, 0xA9])
    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK=1

    emit([0xF0, 0xA9])
    emit([0x12])               # write active

    emit([0x7A])
    emit([0xEE, 0x04])
    emit([0x57])
    emit([0xF0, 0xA9])
    emit([0x12])               # write other

    emit([0x7A])
    emit([0xEE, 0x04])
    emit([0x57])

    emit([0xAF])
    emit([0xE0, 0x4F])        # VBK=0

    emit([0xC1])               # POP BC
    emit([0x05])               # DEC B
    emit_jr_back(0x20, 'p2_col_row')

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


def build_v273():
    """Build v2.73 ROM."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)
    palettes = load_palettes_from_yaml(palette_yaml)

    pal_addr = 0x6800
    boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0

    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    bg_colorizer_addr = 0x6C00
    cond_pal_addr = 0x6D00  # start further out to leave room
    combined_addr = 0x6D80
    bg_table_addr = 0x6E00

    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    cond_pal = create_conditional_palette(pal_loader_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)
    bg_colorizer = create_bg_colorizer_scroll_triggered(bg_table_addr, bg_colorizer_addr)

    print(f"BG colorizer: {len(bg_colorizer)} bytes (at 0x{bg_colorizer_addr:04X})")

    # Auto-relocate if needed
    if bg_colorizer_addr + len(bg_colorizer) > cond_pal_addr:
        cond_pal_addr = (bg_colorizer_addr + len(bg_colorizer) + 0xF) & ~0xF
        print(f"  Relocated cond_pal to 0x{cond_pal_addr:04X}")
        cond_pal = create_conditional_palette(pal_loader_addr)

    if cond_pal_addr + len(cond_pal) > combined_addr:
        combined_addr = (cond_pal_addr + len(cond_pal) + 0xF) & ~0xF
        print(f"  Relocated combined to 0x{combined_addr:04X}")

    if combined_addr + 16 > bg_table_addr:
        bg_table_addr = (combined_addr + 16 + 0xFF) & ~0xFF
        print(f"  Relocated bg_table to 0x{bg_table_addr:04X}")
        # Regenerate BG colorizer with new table addr
        bg_colorizer = create_bg_colorizer_scroll_triggered(bg_table_addr, bg_colorizer_addr)

    combined = bytearray()
    combined.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    combined.extend([0xCD, cond_pal_addr & 0xFF, cond_pal_addr >> 8])
    combined.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    combined.extend([0xCD, 0x80, 0xFF, 0xC9])

    hook = create_vblank_hook(combined_addr)

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
    rom_path = build_v273()
    print(f"\nBuilt v2.73: {rom_path}")
    print(f"Phase 1: 2 rows/frame sweep (9 frames, ~22% CPU)")
    print(f"Phase 2: 1 maintenance row/frame (~13%) + scroll columns (~5% when scrolling)")
    print(f"vs v2.72: always 2 rows/frame (~26%) - v2.73 saves ~50% BG CPU in steady state")
