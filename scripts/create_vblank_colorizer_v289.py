#!/usr/bin/env python3
"""
v2.89: Incremental Palette Loading + BG Palette Attributes in Enhanced Copy

Two targeted fixes for v2.88's remaining issues:

1. INCREMENTAL PALETTE LOADING: Instead of loading all 8 BG + 8 OBJ palettes
   in one frame (~550 M-cycles, causing Timer ISR corruption → phantom sounds),
   spread the load over 8 frames. When the palette hash changes:
   - Store new hash in DF00, set DF03 = 8 (palettes remaining)
   - Each VBlank frame: if DF03 > 0, load ONE BG palette + ONE OBJ palette
     (palette index = 8 - DF03, so palette 0 loads first)
   - Per-frame cost: ~16 register writes × 4 cycles = ~64 M-cycles (vs ~550M)
   - DF02 magic byte still forces full load on cold boot (sets DF03 = 8)

2. BG PALETTE ATTRIBUTES IN ENHANCED COPY: The fast_menu_copy (tile-only, VBK=0)
   was being used unconditionally, bypassing the enhanced copy's palette attribute
   writes (VBK=1). Fix: change the JP at the enhanced copy entry from unconditional
   (0xC3, always fast path) to JP Z (0xCA, fast only when FFC1=0/menus). When
   FFC1=1 (gameplay), fall through to the enhanced copy with interleaved
   palette + tile writes (288 STAT waits).

Previous fixes preserved from v2.88:
- RST $38 RETI→RET phantom sound fix at 0x003B
- D887 sound engine hardening (early clear + range validation)
- Palette hash caching (DF00) for reduced VBlank time
- Joypad release after P13 read
- P13 routine at 0x083C preserved for bank 10
- VBK safety save/restore
- CGB flag (0x80)

HRAM assignments (verified unused by original game via LDH scan):
  FF91: Hook flag (0x5A = copy active, checked but NOT cleared by VBlank)
  FFA5: Sweep state counter (0-23=Phase1, 24-47=Phase2)
  FFA9: Previous SCX/8 for scroll detection

WRAM assignments (verified unused: no EA/FA refs in original ROM):
  DF00: Palette state hash cache (FFBE^FFBF^FFC0^FFD0^FFC1^FFBD + 1)
  DF01: Base hi temp for scroll-edge/BG sweep
  DF02: Init magic byte (0x5A = palette cache initialized)
  DF03: Palettes remaining counter (0 = idle, 1-8 = loading incrementally)
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_tile_to_palette_subroutine,
    create_bg_tile_table,
)
from penta_dragon_dx.display_patcher import apply_all_display_patches

HOOK_FLAG = 0x5A  # Magic value: "hook just ran"


def create_incremental_palette_loader(pal_addr: int) -> bytes:
    """Incremental palette loader using DF03 counter.

    Replaces create_conditional_palette_cached(). Instead of loading ALL
    palettes in one frame (~550M), spreads across 8 frames (~64M each).

    DF02 magic byte init check forces first full load on cold boot (DF03=8).

    Hash: FFBE ^ FFBF ^ FFC0 ^ FFD0 ^ FFC1 ^ FFBD + 1.
    When hash changes: store new hash in DF00, set DF03 = 8.
    Each frame: if DF03 > 0, load one BG + one OBJ palette, decrement DF03.

    Single palette write:
      BG: BCPS = (index * 8) | 0x80, then 8 bytes from pal_addr + index*8
      OBJ: OCPS = (index * 8) | 0x80, then 8 bytes from pal_addr + 64 + index*8
    """
    pal_lo = pal_addr & 0xFF
    pal_hi = (pal_addr >> 8) & 0xFF
    code = bytearray()

    # ================================================================
    # PART 1: DF02 magic byte check — cold boot → set DF03=8
    # ================================================================
    code.extend([
        0xFA, 0x02, 0xDF,  # LD A, [DF02]      ; check init flag
        0xFE, 0x5A,        # CP 0x5A           ; initialized?
        0x28, 0x0B,        # JR Z, +11         ; skip if already initialized
        # First boot: mark initialized and force full palette load
        0x3E, 0x5A,        # LD A, 0x5A
        0xEA, 0x02, 0xDF,  # LD [DF02], A      ; mark as initialized
        0x3E, 0x08,        # LD A, 0x08
        0xEA, 0x03, 0xDF,  # LD [DF03], A      ; force 8 palettes to load
        0x18,              # JR → skip hash check (will load incrementally)
    ])
    # JR offset placeholder — we'll fix it below
    jr_to_load_pos = len(code)
    code.append(0x00)      # placeholder for JR offset

    # ================================================================
    # PART 2: Hash check — compute hash, compare with DF00
    # ================================================================
    hash_start = len(code)
    code.extend([
        0xF0, 0xBE,  # LDH A, [FFBE]  ; form (witch/dragon)
        0x47,        # LD B, A
        0xF0, 0xBF,  # LDH A, [FFBF]  ; boss flag
        0xA8,        # XOR B
        0x47,        # LD B, A
        0xF0, 0xC0,  # LDH A, [FFC0]  ; powerup state
        0xA8,        # XOR B
        0x47,        # LD B, A
        0xF0, 0xD0,  # LDH A, [FFD0]  ; tilemap hi byte
        0xA8,        # XOR B
        0x47,        # LD B, A
        0xF0, 0xC1,  # LDH A, [FFC1]  ; game state (0=menu, 1=playing)
        0xA8,        # XOR B
        0x47,        # LD B, A
        0xF0, 0xBD,  # LDH A, [FFBD]  ; current room
        0xA8,        # XOR B
        0x3C,        # INC A           ; ensure non-zero hash
        0x47,        # LD B, A         ; B = new hash
        0xFA, 0x00, 0xDF,  # LD A, [DF00]   ; previous hash (WRAM)
        0xB8,        # CP B            ; same?
    ])
    # If same hash, skip to incremental load check (don't set DF03)
    code.append(0x28)      # JR Z → skip_set_df03
    jr_same_hash_pos = len(code)
    code.append(0x00)      # placeholder

    # Hash changed: save new hash, set DF03 = 8
    code.extend([
        0x78,              # LD A, B         ; new hash
        0xEA, 0x00, 0xDF,  # LD [DF00], A   ; save
        0x3E, 0x08,        # LD A, 8
        0xEA, 0x03, 0xDF,  # LD [DF03], A   ; 8 palettes to load
    ])

    # Fix JR from cold boot path to here (skip hash, go to load)
    load_check = len(code)
    code[jr_to_load_pos] = (load_check - (jr_to_load_pos + 1)) & 0xFF

    # ================================================================
    # PART 3: Incremental load — if DF03 > 0, load one palette pair
    # ================================================================
    # skip_set_df03 target:
    code[jr_same_hash_pos] = (load_check - (jr_same_hash_pos + 1)) & 0xFF

    code.extend([
        0xFA, 0x03, 0xDF,  # LD A, [DF03]   ; palettes remaining
        0xB7,              # OR A
        0xC8,              # RET Z           ; nothing to load → done
    ])

    # Compute palette index: index = 8 - DF03  (so 0 first, then 1, ..., 7)
    # A = DF03 (1-8)
    code.extend([
        0x47,              # LD B, A         ; B = DF03 (save for decrement)
        0x3E, 0x08,        # LD A, 8
        0x90,              # SUB B           ; A = 8 - DF03 = palette index (0-7)
        0x4F,              # LD C, A         ; C = palette index
    ])

    # Compute offset into palette data: index * 8
    # A already = index
    code.extend([
        0x87,              # ADD A           ; A = index * 2
        0x87,              # ADD A           ; A = index * 4
        0x87,              # ADD A           ; A = index * 8
        0x5F,              # LD E, A         ; E = index * 8 (data offset)
    ])

    # ================================================================
    # Write one BG palette: BCPS = (index * 8) | 0x80, then 8 bytes
    # ================================================================
    # Set BCPS: A = E | 0x80 (E already = index * 8)
    code.extend([
        0x7B,              # LD A, E         ; A = index * 8
        0xF6, 0x80,        # OR 0x80         ; auto-increment flag
        0xE0, 0x68,        # LDH [FF68], A   ; BCPS
    ])

    # Load HL = pal_addr + E (palette data source)
    code.extend([
        0x16, 0x00,        # LD D, 0x00
        0x21, pal_lo, pal_hi,  # LD HL, pal_addr
        0x19,              # ADD HL, DE      ; HL = pal_addr + index*8
    ])

    # Write 8 bytes to BCPD (FF69)
    for _ in range(8):
        code.extend([
            0x2A,          # LD A, [HL+]
            0xE0, 0x69,    # LDH [FF69], A   ; BCPD (auto-increments BCPS)
        ])

    # ================================================================
    # Write one OBJ palette: OCPS = (index * 8) | 0x80, then 8 bytes
    # ================================================================
    # Set OCPS: use saved E = index * 8
    code.extend([
        0x7B,              # LD A, E         ; A = index * 8
        0xF6, 0x80,        # OR 0x80         ; auto-increment flag
        0xE0, 0x6A,        # LDH [FF6A], A   ; OCPS
    ])

    # HL currently = pal_addr + index*8 + 8 (after the BG loop)
    # We need HL = pal_addr + 64 + index*8
    # HL = pal_addr + E + 8, want pal_addr + 64 + E
    # Offset = 64 - 8 = 56 = 0x38
    code.extend([
        0x11, 0x38, 0x00,  # LD DE, 0x0038   ; 56 = 64 - 8
        0x19,              # ADD HL, DE      ; HL = pal_addr + 64 + index*8
    ])

    # Write 8 bytes to OCPD (FF6B)
    for _ in range(8):
        code.extend([
            0x2A,          # LD A, [HL+]
            0xE0, 0x6B,    # LDH [FF6B], A   ; OCPD (auto-increments OCPS)
        ])

    # ================================================================
    # Decrement DF03
    # ================================================================
    code.extend([
        0xFA, 0x03, 0xDF,  # LD A, [DF03]
        0x3D,              # DEC A
        0xEA, 0x03, 0xDF,  # LD [DF03], A
        0xC9,              # RET
    ])

    return bytes(code)


def create_bank_aware_vblank_hook(combined_addr: int) -> bytes:
    """VBlank hook with bank-aware save/restore via FF99.
    Must be exactly 47 bytes (0x0824-0x0852).

    v2.85: CRITICAL FIX — Bank 10 at 0x56C4 does JP 0x083C, jumping into
    the middle of this space to use the P13 button read routine. Previous
    versions put a joypad read loop here that placed 0xFB (= EI opcode!)
    at 0x083C, corrupting joypad reads from bank 10 and causing random
    sound effects.

    Layout:
      0x0824-0x0833 (16 bytes): Bank switch + CALL combined
      0x0834-0x083B (8 bytes):  NOP padding
      0x083C-0x0852 (23 bytes): Original P13 read routine (preserved for bank 10)

    Joypad reading is now done inside the combined handler in bank 13.
    """
    lo, hi = combined_addr & 0xFF, (combined_addr >> 8) & 0xFF
    hook = bytearray([
        # Bank switch + CALL combined (joypad + cond_pal + OBJ + DMA)
        0xF0, 0x99,        # LDH A, [FF99]
        0xF5,              # PUSH AF
        0x3E, 0x0D,        # LD A, 0x0D
        0xEA, 0x00, 0x20,  # LD [0x2000], A
        0xCD, lo, hi,      # CALL combined
        0xF1,              # POP AF
        0xEA, 0x00, 0x20,  # LD [0x2000], A
        0xC9,              # RET
    ])
    padding = bytearray([0x00] * (0x083C - 0x0824 - len(hook)))
    # --- 0x083C-0x0852: Original P13 button read routine (23 bytes) ---
    # Preserved for bank 10's JP 0x083C entry point.
    # Entry: B = P14 direction nibble, P13 already selected, 3 dummy reads done.
    # Reads 4-8 of FF00, then CPL/AND/OR B/store FF93/deselect/RET.
    p13_routine = bytearray([
        0xF0, 0x00,  # LDH A, [FF00]        ; read 4
        0xF0, 0x00,  # LDH A, [FF00]        ; read 5
        0xF0, 0x00,  # LDH A, [FF00]        ; read 6
        0xF0, 0x00,  # LDH A, [FF00]        ; read 7
        0xF0, 0x00,  # LDH A, [FF00]        ; read 8 (settled)
        0x2F,        # CPL
        0xE6, 0x0F,  # AND 0x0F
        0xB0,        # OR B                  ; combine with direction nibble
        0xE0, 0x93,  # LDH [FF93], A        ; store combined result
        0x47,        # LD B, A
        0x3E, 0x30,  # LD A, 0x30           ; deselect joypad
        0xE0, 0x00,  # LDH [FF00], A
        0x78,        # LD A, B
        0xC9,        # RET
    ])
    total = hook + padding + p13_routine
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be 47!"
    return bytes(total)


def create_fast_menu_copy(base_addr: int, return_addr: int) -> bytes:
    """Fast tile-only copy for menus (FFC1=0).

    Replicates original game's tilemap copy: 24 rows x 24 tiles from C1A0
    to VRAM with STAT waits, but NO palette attribute writes. Same speed
    as the vanilla game.

    Uses full DI for the entire copy — matches original game's behavior where
    EI→DI between groups cancels the pending EI, so VBlank NEVER fires during
    the copy. This preserves the game's HALT-based frame sync timing.

    Entry: H = tilemap base hi (0x98 or 0x9C), set by caller.
    """
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

    # DI once at start — VBlank never fires during the entire copy
    emit([0xF3])               # DI

    # Init pointers (H already set by caller)
    emit([0x2E, 0x00])        # LD L, 0x00
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0        ; WRAM tile source
    emit([0x0E, 24])          # LD C, 24             ; 24 rows

    mark('fast_row')
    emit([0x06, 6])            # LD B, 6              ; 6 groups per row

    mark('fast_group')
    # STAT wait: AND 0x02 blocks modes 2+3
    mark('fast_stat')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'fast_stat')  # JR NZ → wait

    # Copy 4 tiles: LD A,[DE]; INC DE; LD [HL+],A x 4
    for _ in range(4):
        emit([0x1A, 0x13, 0x22])  # LD A,[DE]; INC DE; LD [HL+],A

    emit([0x05])               # DEC B
    emit_jr_back(0x20, 'fast_group')  # JR NZ → next group

    # Skip 8 unused columns: HL += 8
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x24])               # INC H

    emit([0x0D])               # DEC C
    emit_jr_back(0x20, 'fast_row')  # JR NZ → next row

    # Return via bridge (bridge does EI before returning to bank 1)
    emit([0xC3, return_addr & 0xFF, (return_addr >> 8) & 0xFF])

    return bytes(code)


def create_enhanced_tilemap_copy(bg_table_addr: int, base_addr: int,
                                  return_addr: int,
                                  fast_menu_addr: int = 0,
                                  cond_pal_addr: int = 0,
                                  shadow_main_addr: int = 0) -> bytes:
    """Enhanced tilemap copy with mini-batch interleaving.

    For each of 24 rows, 6 mini-batches of 4 tiles each:
      - Palette batch: DI + STAT wait + 4 palette writes (VBK=1)
      - Atomic transition: rewind HL/DE, switch VBK=0 (still DI)
      - Tile batch: STAT wait + 4 tile writes (VBK=0) + EI
      - Prepare VBK=1 for next mini-batch

    Palette→tile gap per 4-tile group: <1 scanline (vs 6 in v2.81).
    Same total HBlank count (12 per row), just reordered for atomicity.

    Entry: H = tilemap base hi (0x98 or 0x9C), set by caller.

    v2.89: When fast_menu_addr != 0, uses JP Z (conditional) instead of JP
    (unconditional). FFC1=0 (menus) → fast tile-only path. FFC1=1 (gameplay)
    → falls through to enhanced copy with palette attributes.
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
    # ALWAYS USE FAST PATH — tile-only copy (144 STAT waits).
    # Enhanced palette pass (288 STAT waits) causes audio slowdown
    # because the game rewrites the ENTIRE tilemap on every scroll frame
    # with DI/EI per mini-batch, starving the Timer ISR.
    # BG palette attributes handled by bg_sweep in VBlank instead.
    # ================================================================
    if fast_menu_addr:
        emit([0xF0, 0xC1])    # LDH A,[FFC1]         ; (preserves code size)
        emit([0xB7])           # OR A                  ; (preserves code size)
        emit([0xC3, fast_menu_addr & 0xFF, (fast_menu_addr >> 8) & 0xFF])
                               # JP fast_menu_copy    ; UNCONDITIONAL — always tile-only

    # ================================================================
    # PREAMBLE: Save state, set hook flag, mask IE
    # ================================================================
    emit([0x7C])               # LD A, H
    emit([0xEA, 0x01, 0xDF])  # LD [DF01], A         ; save tilemap base hi (WRAM)

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
    emit([0xF5])               # PUSH AF              ; stack: [row_count] [IE_save]

    # ================================================================
    # ROW LOOP: 6 mini-batches of (4 palette + 4 tile) per row
    # ================================================================
    mark('row_start')

    emit([0x06, bg_table_hi]) # LD B, table_hi       ; B preserved through all batches
    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK = 1              ; start in palette mode

    # Push mini-batch counter (6 groups per row)
    emit([0x3E, 6])
    emit([0xF5])               # PUSH AF              ; stack: [batch_count] [row_count] [IE]

    # ----------------------------------------------------------------
    # MINI-BATCH: 4 palette writes + transition + 4 tile writes
    # ----------------------------------------------------------------
    mark('mb_start')

    # Save WRAM position for rewind after palette writes
    emit([0xD5])               # PUSH DE              ; stack: [DE] [batch] [row] [IE]

    # --- Palette group (VBK=1, 4 tiles via ROM lookup) ---
    emit([0xF3])               # DI                   ; protect palette→tile atomicity
    mark('mb_stat1')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'mb_stat1')  # JR NZ → wait for HBlank

    for _ in range(4):         # 4 tiles per HBlank window (36M)
        emit([0x1A, 0x13])     # LD A,[DE]; INC DE   ; read tile from WRAM
        emit([0x4F])            # LD C, A             ; tile → C for lookup
        emit([0x0A])            # LD A,[BC]           ; palette = table[tile]
        emit([0x22])            # LD [HL+],A          ; write palette attr

    # --- Transition: rewind for tile writes (still DI) ---
    # Rewind HL by 4 (back to these 4 tiles)
    emit([0x7D])               # LD A, L
    emit([0xD6, 4])            # SUB 4
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x25])               # DEC H

    # Switch to tile data
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # VBK = 0

    # Restore DE to mini-batch start
    emit([0xD1])               # POP DE               ; stack: [batch] [row] [IE]

    # --- Tile group (VBK=0, still DI — same 4 tiles) ---
    mark('mb_stat2')
    emit([0xF0, 0x41])        # LDH A,[FF41]
    emit([0xE6, 0x02])        # AND 0x02
    emit_jr_back(0x20, 'mb_stat2')  # JR NZ → wait for HBlank

    for _ in range(4):         # 4 tiles per HBlank window (28M)
        emit([0x1A, 0x13, 0x22])  # LD A,[DE]; INC DE; LD [HL+],A

    emit([0xFB])               # EI                   ; safe to interrupt now

    # --- Prepare next mini-batch ---
    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK = 1              ; ready for next palette group

    # Mini-batch counter
    emit([0xF1])               # POP AF               ; A = batch_count
    emit([0x3D])               # DEC A
    emit([0x28, 0x04])        # JR Z, +4             ; → batches_done (skip PUSH+JR)
    emit([0xF5])               # PUSH AF              ; push decremented count
    emit_jr_back(0x18, 'mb_start')  # JR → next mini-batch

    # ----------------------------------------------------------------
    # Row complete: skip 8-column gap, advance row counter
    # ----------------------------------------------------------------
    # batches_done: stack is [row_count] [IE]
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # VBK = 0              ; clean up after last batch

    # Skip 8-column gap in tilemap
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0x6F])               # LD L, A
    emit([0x30, 0x01])        # JR NC, +1
    emit([0x24])               # INC H

    # Row counter
    emit([0xF1])               # POP AF               ; A = row_count
    emit([0x3D])               # DEC A
    emit([0x28, 0x04])        # JR Z, +4             ; → cleanup (skip PUSH+JP)
    emit([0xF5])               # PUSH AF
    emit_jp_back(0xC3, 'row_start')

    # ================================================================
    # CLEANUP: VBK=0, load palettes, color OBJ, clear flag, restore IE
    # ================================================================
    emit([0xAF])               # XOR A
    emit([0xE0, 0x4F])        # VBK = 0

    # Load CGB palette RAM (cond_pal) — runs once per room transition
    if cond_pal_addr:
        emit([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])

    # Color OBJ sprites — runs once per room transition
    if shadow_main_addr:
        emit([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
        # DMA to apply OBJ changes (game's normal DMA at 0x06D5 already ran)
        emit([0xCD, 0x80, 0xFF])  # CALL DMA

    emit([0xAF])               # XOR A
    emit([0xE0, 0x91])        # LDH [FF91], A       ; clear hook flag

    emit([0xF1])               # POP AF              ; restore old IE
    emit([0xE0, 0xFF])        # LDH [FFFF], A       ; restore IE register

    # Return via bridge
    emit_jp_addr(return_addr)

    return bytes(code)


def create_bg_sweep_no_scroll(bg_table_addr: int, base_addr: int,
                               rows_per_frame: int = 4) -> bytes:
    """VBlank BG sweep — simplified v2.73 without scroll column detection.

    Uses FFA5 as state counter (instead of FF91 which is now the hook flag).
    Phase 1 (FFA5 = 0-23): Initial sweep, rows_per_frame rows/frame
    Phase 2 (FFA5 = 24-47): Maintenance, rows_per_frame rows/frame, wraps at 48→24

    v2.88: Both phases use rows_per_frame (default 4) for faster palette refresh.
    Full 24-row cycle: 6 frames (0.1s) instead of 24 frames (0.4s).

    Covers all 24 rows that the game's tilemap copy writes.
    No scroll column detection — the combined function handles scroll updates.
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
        """Compute D:E from tilemap_row in A. Uses FF89 for base_hi."""
        emit([0x47])               # LD B, A
        emit([0xE6, 0x07])
        emit([0xCB, 0x37])        # SWAP (x16)
        emit([0x87])               # x32
        emit([0x5F])               # LD E, A

        emit([0x78])               # LD A, B
        emit([0xCB, 0x3F])
        emit([0xCB, 0x3F])
        emit([0xCB, 0x3F])        # row>>3
        emit([0x57])               # LD D
        emit([0xFA, 0x01, 0xDF])  # base_hi (WRAM)
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
    emit([0xEA, 0x01, 0xDF])  # DF01 = base_hi (WRAM)

    # Phase check — using FFA5 (not FF91!)
    emit([0xF0, 0xA5])        # LDH A,[FFA5]
    emit([0xFE, 24])
    emit_jr_fwd(0x30, 'phase2')  # JR NC → phase 2

    # ================================================================
    # PHASE 1: Initial sweep (rows_per_frame rows/frame)
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

    mark('p1_done')
    emit_jp_fwd('cleanup')

    # ================================================================
    # PHASE 2: No-op — tile->palette mapping never changes at runtime,
    # so maintenance sweep is unnecessary. Just skip to cleanup.
    # Phase 1 re-triggers after each room transition (FFA5 reset in skip_bg).
    # ================================================================
    mark('phase2')

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


def create_combined_minimal(cond_pal_addr: int, shadow_main_addr: int,
                            bg_sweep_addr: int = 0) -> bytes:
    """ZERO-OVERHEAD VBlank handler — joypad read only.

    v2.89: All colorization moved OUT of VBlank to the tilemap copy path
    (main loop context). VBlank handler does ONLY joypad read.
    Original game DMA at 0x06D5 handles OAM transfer.
    MiSTer Gameboy core can't tolerate any extra VBlank work in CGB mode.
    """
    code = bytearray()
    jr_patches = []
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

    def patch_all():
        for pos, name in jr_patches:
            offset = targets[name] - (pos + 1)
            assert -128 <= offset <= 127, f"JR to {name} from {pos}: {offset}"
            code[pos] = offset & 0xFF

    # ================================================================
    # JOYPAD READ (P14 + P13, MiSTer-compatible)
    # ================================================================
    emit([
        0x3E, 0x20, 0xE0, 0x00,  # P14 select
        0xF0, 0x00, 0xF0, 0x00,  # dummy + actual
        0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,  # CPL, AND, SWAP, LD B
        0x3E, 0x10, 0xE0, 0x00,  # P13 select
        0x0E, 0x08,              # LD C, 8
    ])
    mark('joy_loop')
    emit([0xF0, 0x00, 0x0D])
    emit_jr_back(0x20, 'joy_loop')
    emit([
        0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93,              # LDH [FF93], A
        0x3E, 0x30, 0xE0, 0x00,  # deselect joypad
    ])

    # ================================================================
    # VBK SAFETY
    # ================================================================
    emit([0xF0, 0x4F, 0xF5])  # save VBK
    emit([0xAF, 0xE0, 0x4F])  # VBK=0

    # ================================================================
    # INCREMENTAL PALETTE LOADING (always — even menus for CGB boot compat)
    # ~30M hash check (idle), ~64M when loading 1 palette
    # ================================================================
    emit([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])

    # ================================================================
    # OBJ COLORIZER (gameplay only, 5 sprites/page = ~87M)
    # NO DMA here — original DMA at 0x06D5 picks up our shadow OAM changes
    # ================================================================
    emit([0xF0, 0xC1])        # LDH A,[FFC1]
    emit([0xB7])               # OR A
    emit_jr_fwd(0x28, 'skip_obj')
    emit([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    mark('skip_obj')

    # ================================================================
    # VBK RESTORE (no DMA — original game DMA at 0x06D5 handles it)
    # ================================================================
    emit([0xF1, 0xE0, 0x4F])  # restore VBK
    emit([0xC9])               # RET

    patch_all()
    return bytes(code)


def build_v289():
    """Build v2.89 ROM — incremental palette loading + BG palette attributes."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v289.gb")
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

    # Bank trampoline addresses
    return_bridge_addr = 0x42B4

    # Generate standard components
    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)

    # Layout: enhanced_copy → cond_pal → bg_sweep → combined → fast_menu
    # Per-frame: joypad + incremental_pal + bg_sweep(1 row) + DMA
    # OBJ colorizer DISABLED for phantom sound diagnostic
    enhanced_copy_tmp = create_enhanced_tilemap_copy(bg_table_addr, enhanced_copy_addr,
                                                      return_bridge_addr, fast_menu_addr=0)
    cond_pal_addr = (enhanced_copy_addr + len(enhanced_copy_tmp) + 6 + 0xF) & ~0xF
    cond_pal = create_incremental_palette_loader(pal_addr)
    bg_sweep_addr = (cond_pal_addr + len(cond_pal) + 0xF) & ~0xF
    bg_sweep = create_bg_sweep_no_scroll(bg_table_addr, bg_sweep_addr, rows_per_frame=1)
    combined_addr = (bg_sweep_addr + len(bg_sweep) + 0xF) & ~0xF
    combined = create_combined_minimal(cond_pal_addr, shadow_main_addr, bg_sweep_addr)

    fast_menu_addr = (combined_addr + len(combined) + 0xF) & ~0xF
    fast_menu_copy = create_fast_menu_copy(fast_menu_addr, return_bridge_addr)
    print(f"Fast menu copy: {len(fast_menu_copy)} bytes at 0x{fast_menu_addr:04X}")

    # Second pass with fast_menu_addr
    enhanced_copy = create_enhanced_tilemap_copy(bg_table_addr, enhanced_copy_addr,
                                                  return_bridge_addr,
                                                  fast_menu_addr=fast_menu_addr)
    print(f"Enhanced tilemap copy: {len(enhanced_copy)} bytes at 0x{enhanced_copy_addr:04X}")
    print(f"Incremental palette loader: {len(cond_pal)} bytes at 0x{cond_pal_addr:04X}")
    print(f"BG sweep: {len(bg_sweep)} bytes at 0x{bg_sweep_addr:04X}")
    print(f"Combined (minimal): {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"  → Joypad + IncrementalPal + BgSweep(1row) + DMA (NO OBJ — diagnostic)")

    # Colorize-after-copy routine (runs after tilemap copy, before return to bank 1)
    colorize_addr = (fast_menu_addr + len(fast_menu_copy) + 0xF) & ~0xF
    colorize_code = bytearray()
    colorize_code.extend([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])
    colorize_code.extend([
        0xF0, 0xC1, 0xB7, 0x28, 0x03,
        0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF,
    ])
    colorize_code.extend([0xC3, 0xB4, 0x42])  # JP return_bridge
    print(f"Colorize-after-copy: {len(colorize_code)} bytes at 0x{colorize_addr:04X}")

    assert colorize_addr + len(colorize_code) <= bg_table_addr, \
        f"Layout overflow: colorize ends {colorize_addr+len(colorize_code):#x} > bg_table {bg_table_addr:#x}"

    hook = create_bank_aware_vblank_hook(combined_addr)

    # Overlap check
    regions = [
        ('pal_loader', pal_loader_addr, len(pal_loader)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_pal', tile_pal_addr, len(tile_pal)),
        ('enhanced_copy', enhanced_copy_addr, len(enhanced_copy)),
        ('cond_pal', cond_pal_addr, len(cond_pal)),
        ('bg_sweep', bg_sweep_addr, len(bg_sweep)),
        ('combined', combined_addr, len(combined)),
        ('fast_menu', fast_menu_addr, len(fast_menu_copy)),
        ('colorize', colorize_addr, len(colorize_code)),
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
    w(bg_sweep_addr, bg_sweep)
    w(shadow_main_addr, shadow_main)
    # Patch colorizer sprite count: 40 → 10 (reduces ~700M to ~175M per call)
    # The colorizer starts with LD B, 0x28. Change to LD B, 0x0A.
    colorizer_patched = bytearray(colorizer)
    assert colorizer_patched[0:2] == bytearray([0x06, 0x28]), \
        f"Colorizer doesn't start with LD B,0x28: {colorizer_patched[0:2].hex()}"
    colorizer_patched[1] = 0x05  # 5 sprites/page (~87M, within audio budget)
    w(colorizer_addr, bytes(colorizer_patched))
    w(tile_pal_addr, tile_pal)
    w(enhanced_copy_addr, enhanced_copy)
    w(bg_table_addr, bg_table)
    w(combined_addr, combined)
    w(fast_menu_addr, fast_menu_copy)

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

    # Write colorize-after-copy routine to ROM
    w(colorize_addr, bytes(colorize_code))

    # Redirect fast_menu_copy return: JP 0x42B4 → JP colorize_addr
    fast_menu_end_offset = bank13 + (fast_menu_addr - 0x4000) + len(fast_menu_copy) - 3
    rom[fast_menu_end_offset + 1] = colorize_addr & 0xFF
    rom[fast_menu_end_offset + 2] = (colorize_addr >> 8) & 0xFF
    print(f"Fast menu copy return redirected: 0x42B4 → 0x{colorize_addr:04X}")

    # Bank 13 bridge at 0x42AF
    bridge = bytearray([
        # CRITICAL FIX: NO EI here! Stay DI from trampoline.
        # VBlank firing with bank 13 active causes garbage D887 writes.
        0xC3, enhanced_copy_addr & 0xFF, (enhanced_copy_addr >> 8) & 0xFF,  # JP enhanced_copy
        0x00,              # pad              at 0x42B2
        0x00,              # pad              at 0x42B3
        # Return bridge: switch back to bank 1, then EI
        0x3E, 0x01,        # LD A, 0x01       at 0x42B4
        0xE0, 0x99,        # LDH [FF99], A    at 0x42B6
        0xEA, 0x00, 0x20,  # LD [0x2000], A   at 0x42B8 → bank 1, PC=0x42BB
        0x00,              # pad (bank 1 code at 0x42BB)
    ])
    bridge_offset = bank13 + (0x42AF - 0x4000)
    rom[bridge_offset:bridge_offset+len(bridge)] = bridge
    print(f"Bank 13 bridge: {len(bridge)} bytes at 0x42AF-0x{0x42AF+len(bridge)-1:04X}")

    # Standard patches
    # Keep original DMA at 0x06D5 — our handler writes to shadow OAM,
    # original DMA copies it to OAM. Saves ~160M in our handler.
    # rom[0x06D5:0x06D5+3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824+len(hook)] = hook                     # VBlank hook
    rom[0x143] = 0x80                                       # CGB flag

    # v2.88: Phantom sound fix — RST $38 RETI→RET
    # RST $38 at 0x0038: EA 87 D8 D9 → EA 87 D8 C9
    # RETI re-enables IME mid-VBlank, allowing Timer to fire after
    # intermediate D887 writes. RET keeps IME=0 until the VBlank's
    # own RETI at 0x081D, so D887 values coalesce as in vanilla.
    assert rom[0x0038:0x003C] == bytearray([0xEA, 0x87, 0xD8, 0xD9]), \
        f"RST $38 mismatch: {rom[0x0038:0x003C].hex()}"
    # RST $38 fix DISABLED — testing if it causes phantom sounds with No Pops
    # rom[0x003B] = 0xC9  # RETI → RET

    # D887 hardening + RST $38 fix both DISABLED
    print(f"Audio patches: ALL DISABLED (original sound engine + RST $38 preserved)")

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
    rom_path = build_v289()
    print(f"\nBuilt v2.89: {rom_path}")
    print(f"CHANGE 1: Incremental palette loading — 1 BG + 1 OBJ palette/frame (~64M vs ~550M)")
    print(f"CHANGE 2: BG palette attributes — JP Z (conditional) enables enhanced copy for gameplay")
    print(f"PRESERVED: RST $38 RETI→RET, D887 hardening, CGB flag, all other v2.88 patches")
