#!/usr/bin/env python3
"""
v2.90: Inline BG Attribute Pass -- Zero Scroll Artifacts

KEY CHANGE: After the fast tile copy (VBK=0), an inline attribute pass
writes palette attributes (VBK=1) for the entire tilemap using the same
C1A0 WRAM buffer as source. This runs in main-loop context (not VBlank).

Flow per tilemap copy:
  1. Fast tile copy: DI, 24 rows x 6 groups of 4 tiles (144 STAT waits)
  2. BG attribute pass (two-phase per row):
     Phase 1: Build 24 palette attrs in DF10-DF27 from C1A0 (no STAT waits)
     Phase 2: Copy 24 attrs to VRAM VBK=1 (3 groups x 8 attrs = 72 STAT waits)
  3. Colorize: cond_pal (incremental palette load) + OBJ colorizer
  4. Return to bank 1 via bridge (EI there)

Total STAT waits: 216 (144 tile + 72 attr). Old approach: 288 (144 + 144).
The 8-attrs-per-HBlank optimization (8*6M=48M, fits in 51M window) halves
the VRAM access phase cost.

Previous fixes preserved from v2.89:
- Incremental palette loading (8 frames, ~64M each)
- Joypad release after P13 read
- P13 routine at 0x083C preserved for bank 10
- VBK safety save/restore
- CGB flag (0x80)

HRAM assignments:
  FFA9: Temp tilemap base hi (used by attr pass)

WRAM assignments:
  DF00: Palette state hash cache
  DF01: Tilemap base hi (saved by enhanced copy entry)
  DF02: Init magic byte (0x5A = palette cache initialized)
  DF03: Palettes remaining counter (0=idle, 1-8=loading)
  DF05: VRAM row pointer low byte (used by attr pass)
  DF10-DF27: 24-byte row attribute buffer (used by attr pass)
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

HOOK_FLAG = 0x5A


def create_incremental_palette_loader(pal_addr: int) -> bytes:
    """Incremental palette loader using DF03 counter.

    Hash: FFBE ^ FFBF ^ FFC0 ^ FFD0 ^ FFC1 ^ FFBD + 1.
    When hash changes: store new hash in DF00, set DF03 = 8.
    Each frame: if DF03 > 0, load one BG + one OBJ palette, decrement DF03.
    """
    pal_lo = pal_addr & 0xFF
    pal_hi = (pal_addr >> 8) & 0xFF
    code = bytearray()

    # DF02 magic byte check -- cold boot -> set DF03=8
    code.extend([
        0xFA, 0x02, 0xDF,  # LD A, [DF02]
        0xFE, 0x5A,        # CP 0x5A
        0x28, 0x0B,        # JR Z, +11
        0x3E, 0x5A,        # LD A, 0x5A
        0xEA, 0x02, 0xDF,  # LD [DF02], A
        0x3E, 0x08,        # LD A, 0x08
        0xEA, 0x03, 0xDF,  # LD [DF03], A
        0x18,              # JR
    ])
    jr_to_load_pos = len(code)
    code.append(0x00)

    # Hash check
    code.extend([
        0xF0, 0xBE,  0x47,
        0xF0, 0xBF,  0xA8, 0x47,
        0xF0, 0xC0,  0xA8, 0x47,
        0xF0, 0xD0,  0xA8, 0x47,
        0xF0, 0xC1,  0xA8, 0x47,
        0xF0, 0xBD,  0xA8,
        0x3C, 0x47,
        0xFA, 0x00, 0xDF,
        0xB8,
    ])
    code.append(0x28)
    jr_same_hash_pos = len(code)
    code.append(0x00)

    # Hash changed
    code.extend([
        0x78, 0xEA, 0x00, 0xDF,
        0x3E, 0x08, 0xEA, 0x03, 0xDF,
    ])

    load_check = len(code)
    code[jr_to_load_pos] = (load_check - (jr_to_load_pos + 1)) & 0xFF
    code[jr_same_hash_pos] = (load_check - (jr_same_hash_pos + 1)) & 0xFF

    # Incremental load
    code.extend([
        0xFA, 0x03, 0xDF,
        0xB7, 0xC8,
        0x47, 0x3E, 0x08, 0x90, 0x4F,
        0x87, 0x87, 0x87, 0x5F,
    ])

    # Write one BG palette
    code.extend([
        0x7B, 0xF6, 0x80, 0xE0, 0x68,
        0x16, 0x00, 0x21, pal_lo, pal_hi, 0x19,
    ])
    for _ in range(8):
        code.extend([0x2A, 0xE0, 0x69])

    # Write one OBJ palette
    code.extend([
        0x7B, 0xF6, 0x80, 0xE0, 0x6A,
        0x11, 0x38, 0x00, 0x19,
    ])
    for _ in range(8):
        code.extend([0x2A, 0xE0, 0x6B])

    # Decrement DF03
    code.extend([
        0xFA, 0x03, 0xDF, 0x3D, 0xEA, 0x03, 0xDF, 0xC9,
    ])

    return bytes(code)


def create_bank_aware_vblank_hook(combined_addr: int) -> bytes:
    """VBlank hook: bank switch + CALL combined + restore. Must be 47 bytes."""
    lo, hi = combined_addr & 0xFF, (combined_addr >> 8) & 0xFF
    hook = bytearray([
        0xF0, 0x99, 0xF5,
        0x3E, 0x0D, 0xEA, 0x00, 0x20,
        0xCD, lo, hi,
        0xF1, 0xEA, 0x00, 0x20,
        0xC9,
    ])
    padding = bytearray([0x00] * (0x083C - 0x0824 - len(hook)))
    p13_routine = bytearray([
        0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xB0, 0xE0, 0x93,
        0x47, 0x3E, 0x30, 0xE0, 0x00, 0x78, 0xC9,
    ])
    total = hook + padding + p13_routine
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be 47!"
    return bytes(total)


def create_fast_menu_copy(base_addr: int, return_addr: int) -> bytes:
    """Fast tile-only copy: 24 rows x 6 groups of 4 tiles (144 STAT waits)."""
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

    emit([0xF3])               # DI
    emit([0x2E, 0x00])        # LD L, 0x00
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0
    emit([0x0E, 24])          # LD C, 24

    mark('fast_row')
    emit([0x06, 6])            # LD B, 6

    mark('fast_group')
    mark('fast_stat')
    emit([0xF0, 0x41])
    emit([0xE6, 0x02])
    emit_jr_back(0x20, 'fast_stat')

    for _ in range(4):
        emit([0x1A, 0x13, 0x22])

    emit([0x05])
    emit_jr_back(0x20, 'fast_group')

    emit([0x7D])
    emit([0xC6, 0x08])
    emit([0x6F])
    emit([0x30, 0x01])
    emit([0x24])

    emit([0x0D])
    emit_jr_back(0x20, 'fast_row')

    emit([0xC3, return_addr & 0xFF, (return_addr >> 8) & 0xFF])
    return bytes(code)


def create_bg_attr_pass(bg_table_addr: int, base_addr: int,
                        cond_pal_addr: int, shadow_main_addr: int,
                        return_bridge_addr: int) -> bytes:
    """BG attribute pass -- two-phase per row, 8 attrs per STAT window.

    Phase 1: Read 24 tiles from C1A0, lookup palette in ROM table,
             write 24 attrs to DF10-DF27 (WRAM buffer, no STAT waits).
    Phase 2: Copy 24 attrs from DF10 to VRAM VBK=1 with STAT waits.
             3 groups of 8 attrs per HBlank (8*6M=48M, fits 51M window).
             Total: 72 STAT waits for all 24 rows.

    Entry: DI active, DF01 = tilemap base hi.
    Exit: JP return_bridge (EI + bank switch).
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

    # CHECK: Only during gameplay (FFC1=1)
    emit([0xF0, 0xC1])        # LDH A,[FFC1]
    emit([0xB7])               # OR A
    jr_skip_pos = len(code)
    emit([0x28, 0x00])        # JR Z -> skip (placeholder)

    # Setup
    emit([0xFA, 0x01, 0xDF])  # LD A, [DF01] ; tilemap base hi
    emit([0xE0, 0xA9])        # LDH [FFA9], A
    emit([0x11, 0xA0, 0xC1]) # LD DE, 0xC1A0
    emit([0x0E, 24])          # LD C, 24 rows
    emit([0xAF])               # XOR A
    emit([0xEA, 0x05, 0xDF])  # LD [DF05], A ; VRAM L offset = 0

    # === ROW LOOP ===
    mark('row_loop')
    emit([0xC5])               # PUSH BC ; save row count

    # --- Phase 1: Build 24 palette attrs in DF10-DF27 ---
    emit([0x21, 0x10, 0xDF])  # LD HL, DF10
    emit([0x06, bg_table_hi]) # LD B, table_hi
    emit([0x0E, 24])          # LD C, 24

    mark('p1_loop')
    emit([0x1A])               # LD A, [DE]   ; tile
    emit([0x13])               # INC DE
    emit([0xE5])               # PUSH HL      ; save buf ptr
    emit([0x6F])               # LD L, A      ; L = tile
    emit([0x60])               # LD H, B      ; H = table_hi
    emit([0x7E])               # LD A, [HL]   ; palette
    emit([0xE1])               # POP HL       ; restore buf
    emit([0x22])               # LD [HL+], A  ; write attr
    emit([0x0D])               # DEC C
    emit_jr_back(0x20, 'p1_loop')

    # Save DE (next row in C1A0)
    emit([0xD5])               # PUSH DE

    # --- Phase 2: Copy 24 attrs from DF10 to VRAM VBK=1 ---
    emit([0x3E, 0x01])
    emit([0xE0, 0x4F])        # VBK = 1

    emit([0xF0, 0xA9])        # LD A, [FFA9] ; base hi
    emit([0x67])               # LD H, A
    emit([0xFA, 0x05, 0xDF])  # LD A, [DF05] ; VRAM L
    emit([0x6F])               # LD L, A

    emit([0x11, 0x10, 0xDF]) # LD DE, DF10
    emit([0x06, 3])            # LD B, 3 ; 3 groups of 8

    mark('p2_group')
    mark('p2_stat')
    emit([0xF0, 0x41])
    emit([0xE6, 0x02])
    emit_jr_back(0x20, 'p2_stat')

    # 8 attrs per HBlank (8 * 6M = 48M, fits 51M)
    for _ in range(8):
        emit([0x1A, 0x13, 0x22])

    emit([0x05])               # DEC B
    emit_jr_back(0x20, 'p2_group')

    # VBK = 0
    emit([0xAF])
    emit([0xE0, 0x4F])

    # Advance VRAM row pointer (skip 8-col gap)
    emit([0x7D])               # LD A, L
    emit([0xC6, 0x08])        # ADD 8
    emit([0xEA, 0x05, 0xDF])  # LD [DF05], A
    emit([0x30, 0x04])        # JR NC, +4
    emit([0xF0, 0xA9])
    emit([0x3C])
    emit([0xE0, 0xA9])

    # Restore DE and row counter
    emit([0xD1])               # POP DE
    emit([0xC1])               # POP BC ; C = row count

    emit([0x0D])               # DEC C
    jp_row = base_addr + targets['row_loop']
    emit([0xC2, jp_row & 0xFF, (jp_row >> 8) & 0xFF])

    # === SKIP_TO_COLORIZE ===
    skip_target = len(code)
    code[jr_skip_pos + 1] = (skip_target - (jr_skip_pos + 2)) & 0xFF

    emit([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])

    emit([0xF0, 0xC1])
    emit([0xB7])
    emit([0x28, 0x03])
    emit([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])

    emit([0xC3, return_bridge_addr & 0xFF, (return_bridge_addr >> 8) & 0xFF])
    return bytes(code)


def create_enhanced_tilemap_copy_v290(bg_table_addr: int, base_addr: int,
                                      return_addr: int,
                                      fast_menu_addr: int = 0) -> bytes:
    """Entry point: save H to DF01, jump to fast_menu_copy."""
    code = bytearray()
    code.extend([0x7C])               # LD A, H
    code.extend([0xEA, 0x01, 0xDF])  # LD [DF01], A
    assert fast_menu_addr != 0
    code.extend([0xC3, fast_menu_addr & 0xFF, (fast_menu_addr >> 8) & 0xFF])
    return bytes(code)


def create_combined_minimal(cond_pal_addr: int, shadow_main_addr: int,
                            bg_sweep_addr: int = 0) -> bytes:
    """VBlank handler: joypad + incremental palette + OBJ colorizer."""
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
        assert -128 <= offset <= 127
        emit([opcode, offset & 0xFF])

    def patch_all():
        for pos, name in jr_patches:
            offset = targets[name] - (pos + 1)
            assert -128 <= offset <= 127
            code[pos] = offset & 0xFF

    # Joypad read
    emit([
        0x3E, 0x20, 0xE0, 0x00,
        0xF0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00,
        0x0E, 0x08,
    ])
    mark('joy_loop')
    emit([0xF0, 0x00, 0x0D])
    emit_jr_back(0x20, 'joy_loop')
    emit([
        0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93,
        0x3E, 0x30, 0xE0, 0x00,
    ])

    # VBK safety
    emit([0xF0, 0x4F, 0xF5])
    emit([0xAF, 0xE0, 0x4F])

    # Incremental palette loading
    emit([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])

    # OBJ colorizer (gameplay only)
    emit([0xF0, 0xC1])
    emit([0xB7])
    emit_jr_fwd(0x28, 'skip_obj')
    emit([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    mark('skip_obj')

    # VBK restore
    emit([0xF1, 0xE0, 0x4F])
    emit([0xC9])

    patch_all()
    return bytes(code)


def build_v290():
    """Build v2.90 ROM."""
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v290.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)
    palettes = load_palettes_from_yaml(palette_yaml)

    # Address layout in bank 13
    pal_addr = 0x6800
    boss_pal_addr = 0x6880; boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0

    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    enhanced_copy_addr = 0x6C00
    bg_table_addr = 0x7000

    return_bridge_addr = 0x42B4

    # Generate components
    pal_loader = create_palette_loader(pal_addr, boss_pal_addr, boss_slot_addr,
                                       swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table(ff_filter=False)

    # Layout: enhanced_copy -> cond_pal -> combined -> fast_menu -> bg_attr_pass
    enhanced_copy_tmp = create_enhanced_tilemap_copy_v290(bg_table_addr, enhanced_copy_addr,
                                                          return_bridge_addr, fast_menu_addr=0x7F00)

    cond_pal_addr_val = (enhanced_copy_addr + len(enhanced_copy_tmp) + 0xF) & ~0xF
    cond_pal = create_incremental_palette_loader(pal_addr)

    combined_addr = (cond_pal_addr_val + len(cond_pal) + 0xF) & ~0xF
    combined = create_combined_minimal(cond_pal_addr_val, shadow_main_addr)

    fast_menu_addr = (combined_addr + len(combined) + 0xF) & ~0xF
    fast_menu_tmp = create_fast_menu_copy(fast_menu_addr, 0x7F00)

    bg_attr_pass_addr = (fast_menu_addr + len(fast_menu_tmp) + 0xF) & ~0xF
    bg_attr_pass = create_bg_attr_pass(bg_table_addr, bg_attr_pass_addr,
                                        cond_pal_addr_val, shadow_main_addr,
                                        return_bridge_addr)

    print(f"Enhanced copy entry: {len(enhanced_copy_tmp)} bytes at 0x{enhanced_copy_addr:04X}")
    print(f"Incremental palette loader: {len(cond_pal)} bytes at 0x{cond_pal_addr_val:04X}")
    print(f"Combined (VBlank): {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"Fast menu copy: {len(fast_menu_tmp)} bytes at 0x{fast_menu_addr:04X}")
    print(f"BG attr pass: {len(bg_attr_pass)} bytes at 0x{bg_attr_pass_addr:04X}")

    assert bg_attr_pass_addr + len(bg_attr_pass) <= bg_table_addr, \
        f"Layout overflow: {bg_attr_pass_addr+len(bg_attr_pass):#x} > {bg_table_addr:#x}"

    # Second pass with correct addresses
    enhanced_copy = create_enhanced_tilemap_copy_v290(bg_table_addr, enhanced_copy_addr,
                                                      return_bridge_addr,
                                                      fast_menu_addr=fast_menu_addr)
    fast_menu_copy = create_fast_menu_copy(fast_menu_addr, bg_attr_pass_addr)

    hook = create_bank_aware_vblank_hook(combined_addr)

    # Overlap check
    regions = [
        ('pal_loader', pal_loader_addr, len(pal_loader)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_pal', tile_pal_addr, len(tile_pal)),
        ('enhanced_copy', enhanced_copy_addr, len(enhanced_copy)),
        ('cond_pal', cond_pal_addr_val, len(cond_pal)),
        ('combined', combined_addr, len(combined)),
        ('fast_menu', fast_menu_addr, len(fast_menu_copy)),
        ('bg_attr_pass', bg_attr_pass_addr, len(bg_attr_pass)),
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
    w(cond_pal_addr_val, cond_pal)
    w(shadow_main_addr, shadow_main)
    colorizer_patched = bytearray(colorizer)
    assert colorizer_patched[0:2] == bytearray([0x06, 0x28])
    colorizer_patched[1] = 0x05  # 5 sprites/page
    w(colorizer_addr, bytes(colorizer_patched))
    w(tile_pal_addr, tile_pal)
    w(enhanced_copy_addr, enhanced_copy)
    w(bg_table_addr, bg_table)
    w(combined_addr, combined)
    w(fast_menu_addr, fast_menu_copy)
    w(bg_attr_pass_addr, bg_attr_pass)

    # Bank 1 trampoline at 0x42A7
    bank1_patch = bytearray([
        0xF3,              # DI                at 0x42A7
        0x3E, 0x0D,        # LD A, 0x0D       at 0x42A8
        0xE0, 0x99,        # LDH [FF99], A    at 0x42AA
        0xEA, 0x00, 0x20,  # LD [0x2000], A   at 0x42AC
    ])
    dead_len = 0x42BC - 0x42AF
    bank1_patch.extend([0x00] * dead_len)
    bank1_patch.extend([0xFB, 0xC9])  # EI; RET at 0x42BC-0x42BD
    rom[0x42A7:0x42A7+len(bank1_patch)] = bank1_patch

    # Bank 13 bridge at 0x42AF
    bridge = bytearray([
        0xC3, enhanced_copy_addr & 0xFF, (enhanced_copy_addr >> 8) & 0xFF,
        0x00, 0x00,        # pad at 0x42B2-0x42B3
        # Return bridge at 0x42B4
        0x3E, 0x01,        # LD A, 0x01
        0xE0, 0x99,        # LDH [FF99], A
        0xEA, 0x00, 0x20,  # LD [0x2000], A
        0x00,              # pad at 0x42BB
    ])
    bridge_offset = bank13 + (0x42AF - 0x4000)
    rom[bridge_offset:bridge_offset+len(bridge)] = bridge

    # Standard patches
    rom[0x0824:0x0824+len(hook)] = hook
    rom[0x143] = 0x80  # CGB flag

    # RST $38 fix (disabled for testing)
    assert rom[0x0038:0x003C] == bytearray([0xEA, 0x87, 0xD8, 0xD9])

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
    rom_path = build_v290()
    print(f"\nBuilt v2.90: {rom_path}")
    print(f"  BG attr pass: 3 groups x 8 attrs/STAT = 72 STAT waits (was 144)")
    print(f"  Total: 216 STAT waits (144 tile + 72 attr)")
