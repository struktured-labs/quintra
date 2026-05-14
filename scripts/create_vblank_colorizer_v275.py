#!/usr/bin/env python3
"""
v2.75: Hook-Only BG Colorizer — Zero VBlank BG Cost

Pure O(1) approach: intercept the game's tilemap copy at 0x42A7 to write palette
attributes alongside tile IDs. NO VBlank sweep. All BG coloring happens during
the game's main loop.

KEY INSIGHT: The game's STAT interrupt handler at 0x0853 saves/restores the ROM
bank via FF99. By setting FF99=0x0D during the enhanced copy, STAT interrupts
correctly restore bank 13 on exit. DI/EI wraps only the bank switch transitions
(~8 cycles each), not the entire copy.

VBlank handler: CondPalette + OBJ + DMA only (~4% frame budget)

Flow (hook):
  Caller → 0x42A7 (bank 1: DI, set FF99=0x0D, switch to bank 13)
         → 0x42AF (bank 13: EI, JP 0x6C00)
         → 0x6C00 (enhanced copy: tiles + palettes, interrupts enabled)
         → JP 0x42B4 (bank 13: DI, set FF99=0x01, switch to bank 1)
         → 0x42BC (bank 1: EI, RET)
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


def create_bank_aware_vblank_hook(combined_addr: int) -> bytes:
    """VBlank hook with joypad + bank-aware save/restore via FF99.

    Saves FF99 (game's ROM bank register) before switching to bank 13,
    restores it after handler runs. The STAT handler at 0x0853 also uses
    FF99, so both VBlank and STAT interrupts are bank-safe.

    VBlank runs with IME=0 (no nested interrupts), so no DI needed here.
    Must be exactly 47 bytes (0x0824-0x0852).
    """
    lo, hi = combined_addr & 0xFF, (combined_addr >> 8) & 0xFF
    # Shortened joypad: 2 dummy reads instead of 8-iteration delay loop
    # Safe for CGB (only needs 2 M-cycle settling time)
    joy = bytearray([
        0x3E, 0x20,  # LD A, 0x20        (select direction keys)
        0xE0, 0x00,  # LDH [FF00], A
        0xF0, 0x00,  # LDH A, [FF00]     (read directions)
        0x2F,        # CPL
        0xE6, 0x0F,  # AND 0x0F
        0xCB, 0x37,  # SWAP A
        0x47,        # LD B, A
        0x3E, 0x10,  # LD A, 0x10        (select button keys)
        0xE0, 0x00,  # LDH [FF00], A
        0xF0, 0x00,  # LDH A, [FF00]     (dummy read for settling)
        0xF0, 0x00,  # LDH A, [FF00]     (actual read)
        0x2F,        # CPL
        0xE6, 0x0F,  # AND 0x0F
        0xB0,        # OR B
        0xE0, 0x93,  # LDH [FF93], A     (store combined joypad)
        0x3E, 0x30,  # LD A, 0x30        (deselect joypad)
        0xE0, 0x00,  # LDH [FF00], A
    ])
    # Bank-aware hook: save FF99 on stack, switch to 13, call, restore
    hook = bytearray([
        0xF0, 0x99,        # LDH A, [FF99]    ; read game's bank register
        0xF5,              # PUSH AF           ; save it
        0x3E, 0x0D,        # LD A, 0x0D
        0xEA, 0x00, 0x20,  # LD [0x2000], A    ; switch to bank 13
        0xCD, lo, hi,      # CALL combined
        0xF1,              # POP AF            ; restore saved bank
        0xEA, 0x00, 0x20,  # LD [0x2000], A    ; switch back
        0xC9,              # RET
    ])
    total = joy + hook
    # Pad to exactly 47 bytes if needed
    while len(total) < 47:
        total.append(0x00)
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be 47!"
    return bytes(total)


def create_enhanced_tilemap_copy(bg_table_addr: int, base_addr: int,
                                  return_addr: int) -> bytes:
    """Enhanced tilemap copy: Pass 1 (tiles) + Pass 2 (palette attributes).

    Batched design: 4 tiles per STAT window (matches original game).
    24 cols / 4 = 6 STAT groups per row × 24 rows = 144 STAT waits per pass.
    Total: 288 STAT waits (vs 1152 in per-tile version = 4× faster).

    Runs with interrupts ENABLED. FF99=0x0D ensures STAT handler restores
    bank 13 correctly. VRAM writes may occasionally be dropped if STAT
    interrupts delay past HBlank, but the game re-calls the copy regularly.

    Entry: H = tilemap base hi (0x98 or 0x9C), set by caller.
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
        addr = base_addr + targets[name]
        emit([opcode, addr & 0xFF, (addr >> 8) & 0xFF])

    # Save H to HRAM (needed by Pass 2 to rewind HL)
    emit([0x7C])               # LD A, H
    emit([0xE0, 0xEE])        # LDH [FFEE], A  ; save base_hi

    # ================================================================
    # PASS 1: Tile copy from C1A0 to VRAM
    # 6 groups of 4 tiles per row × 24 rows = 144 STAT waits
    # Registers: HL=VRAM, DE=C1A0, B=6 groups, C=24 rows
    # ================================================================
    emit([0x2E, 0x00])        # LD L, 0x00
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0
    emit([0x0E, 24])          # C = 24 rows

    mark('p1_row')
    emit([0x06, 6])            # B = 6 groups

    mark('p1_group')
    emit([0xF3])               # DI (protect STAT wait + writes from interrupts)
    mark('p1_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'p1_stat')  # JR NZ (wait for HBlank/VBlank)

    # 4 tile copies (12 bytes, ~8 cycles each = 32 cycles, fits HBlank)
    for _ in range(4):
        emit([0x1A, 0x13, 0x22])  # LD A,[DE]; INC DE; LD [HL+],A

    emit([0xFB])               # EI (allow interrupts between groups)
    emit([0x05])               # DEC B (runs with IRQ still off due to EI delay)
    emit_jr_back(0x20, 'p1_group')  # JR NZ

    # Skip 8-column gap: L += 8
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x24])               # INC H

    emit([0x0D])               # DEC C (row counter)
    emit_jp_back(0xC2, 'p1_row')  # JP NZ

    # ================================================================
    # PASS 2: Palette attributes via ROM lookup (VBK=1)
    # 6 groups of 4 palette lookups per row × 24 rows
    # Registers: HL=VRAM attr, DE=C1A0, B=table_hi, C=tile_id (temp)
    #
    # CRITICAL: Counters use STACK, not HRAM!
    # VBlank handler fires between groups (after EI) and corrupts HRAM
    # (FFA5/FFA9/FF91) via the game's VBlank code. But VBlank handler
    # saves/restores CPU registers, so stack-based counters are safe.
    #
    # Stack layout: [row_counter(AF)] pushed at start, popped between rows
    # Group counter: C register, saved via PUSH BC / POP BC per group
    # ================================================================
    emit([0xF0, 0xEE])        # LDH A,[FFEE]
    emit([0x67])               # LD H, A  (base_hi)
    emit([0x2E, 0x00])        # LD L, 0
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0

    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK = 1

    # Push row counter onto stack
    emit([0x3E, 24])          # A = 24 rows
    emit([0xF5])               # PUSH AF  (row counter on stack)

    mark('p2_row')
    emit([0x0E, 6])            # C = 6 groups
    emit([0x06, bg_table_hi]) # B = table_hi

    mark('p2_group')
    emit([0xC5])               # PUSH BC (save B=table_hi, C=group_counter)
    emit([0xF3])               # DI (protect STAT wait + writes)
    mark('p2_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'p2_stat')  # JR NZ (wait for HBlank/VBlank)

    # 4 palette lookups (5 bytes each, ~9 cycles each = 36 cycles)
    for _ in range(4):
        emit([0x1A, 0x13])     # LD A,[DE]; INC DE  ; read tile
        emit([0x4F])            # LD C, A            ; C = tile_id
        emit([0x0A])            # LD A,[BC]          ; palette = table[tile_id]
        emit([0x22])            # LD [HL+],A         ; write palette attr

    emit([0xFB])               # EI (allow interrupts between groups)
    emit([0xC1])               # POP BC (restore B=table_hi, C=group_counter)
    emit([0x0D])               # DEC C (group counter, safe - regs preserved by VBlank)
    emit_jr_back(0x20, 'p2_group')  # JR NZ

    # Skip 8-column gap
    emit([0x7D])
    emit([0xC6, 0x08])
    emit([0x6F])
    emit([0x30, 0x01])
    emit([0x24])

    # Decrement row counter (on stack)
    emit([0xF1])               # POP AF (row counter)
    emit([0x3D])               # DEC A
    emit([0x28, 0x04])        # JR Z, +4 (skip PUSH+JP if done → fall to VBK=0)
    emit([0xF5])               # PUSH AF (save decremented counter)
    emit_jp_back(0xC3, 'p2_row')  # JP p2_row
    # Fall through when done (A=0, row counter exhausted)

    # VBK = 0
    emit([0xAF])
    emit([0xE0, 0x4F])

    # Return via bridge
    emit_jp_addr(return_addr)

    return bytes(code)


def build_v275():
    """Build v2.75 ROM — hook-only, zero VBlank BG cost."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)
    palettes = load_palettes_from_yaml(palette_yaml)

    # Address layout — simplified, no sweep needed
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

    # Bank trampoline addresses
    # Entry: DI + FF99=0x0D + bank switch → bank 13 at 0x42AF
    # Bank 13: EI + JP enhanced_copy
    # Return: DI + FF99=0x01 + bank switch → bank 1 at 0x42BC
    # Bank 1: EI + RET
    return_bridge_addr = 0x42B4  # enhanced copy JPs here

    # Generate components
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

    # Conditional palette (placed after enhanced copy)
    cond_pal_addr = (enhanced_copy_addr + len(enhanced_copy) + 0xF) & ~0xF
    cond_pal = create_conditional_palette(pal_loader_addr)
    print(f"Cond palette: {len(cond_pal)} bytes at 0x{cond_pal_addr:04X}")

    # Combined: CondPalette → OBJ → DMA (NO BG sweep!)
    combined_addr = (cond_pal_addr + len(cond_pal) + 0xF) & ~0xF
    combined = bytearray()
    combined.extend([0xCD, cond_pal_addr & 0xFF, cond_pal_addr >> 8])   # CALL cond_pal
    combined.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])  # CALL OBJ
    combined.extend([0xCD, 0x80, 0xFF])   # CALL DMA (FF80)
    combined.extend([0xC9])               # RET
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"  → NO BG sweep! VBlank = CondPalette + OBJ + DMA only")

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
    w(bg_table_addr, bg_table)
    w(combined_addr, combined)

    # =============================================
    # HOOK: Bank 1 trampoline at 0x42A7
    # =============================================
    # DI protects the FF99 + bank switch from STAT/VBlank interrupts.
    # FF99 is the game's ROM bank register — STAT handler restores from it.
    #
    # Bank 1 entry (0x42A7):
    #   42A7: DI
    #   42A8: LD A, 0x0D
    #   42AA: LDH [FF99], A     (game's bank register = bank 13)
    #   42AC: LD [0x2000], A    (switch to bank 13) → PC=0x42AF
    #   42AF-42BB: dead zone (bank 13 code lives here)
    #   42BC: EI                (after return from bank 13)
    #   42BD: RET
    #
    # Bank 13 forward path (0x42AF):
    #   42AF: EI                (re-enable interrupts, 1-insn delay)
    #   42B0: JP 0x6C00         (enhanced copy)
    #
    # Bank 13 return path (0x42B4, enhanced copy JPs here):
    #   42B4: DI
    #   42B5: LD A, 0x01
    #   42B7: LDH [FF99], A     (restore game's bank register)
    #   42B9: LD [0x2000], A    (switch to bank 1) → PC=0x42BC
    bank1_patch = bytearray([
        0xF3,              # DI                at 0x42A7
        0x3E, 0x0D,        # LD A, 0x0D       at 0x42A8
        0xE0, 0x99,        # LDH [FF99], A    at 0x42AA
        0xEA, 0x00, 0x20,  # LD [0x2000], A   at 0x42AC → bank 13, PC=0x42AF
    ])
    # Dead zone in bank 1: 0x42AF-0x42BB (13 bytes, bank 13 code occupies these)
    dead_len = 0x42BC - 0x42AF  # 13 bytes
    bank1_patch.extend([0x00] * dead_len)
    bank1_patch.extend([
        0xFB,              # EI               at 0x42BC
        0xC9,              # RET              at 0x42BD
    ])
    rom[0x42A7:0x42A7+len(bank1_patch)] = bank1_patch
    print(f"Bank 1 trampoline: {len(bank1_patch)} bytes at 0x42A7-0x{0x42A7+len(bank1_patch)-1:04X}")

    # Bank 13 bridge at 0x42AF (ROM offset bank13 + 0x42AF - 0x4000)
    bridge = bytearray([
        # Forward path (entered from bank switch, interrupts disabled):
        0xFB,              # EI               at 0x42AF (1-insn delay → JP runs w/ IRQ off)
        0xC3, enhanced_copy_addr & 0xFF, (enhanced_copy_addr >> 8) & 0xFF,  # JP 0x6C00
        0x00,              # pad              at 0x42B3
        # Return path (enhanced copy JPs here = 0x42B4):
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
    rom_path = build_v275()
    print(f"\nBuilt v2.75: {rom_path}")
    print(f"Hook-only: O(1) tilemap copy, ZERO VBlank BG cost")
    print(f"VBlank handler: CondPalette + OBJ + DMA only (~4% frame budget)")
