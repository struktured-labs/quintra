#!/usr/bin/env python3
"""
v2.46: Fix BG Colorizer - Inline Comparison (No ROM Lookup Table)

ROOT CAUSE FIX: v2.44/v2.45 used a ROM lookup table at 0x6B00 (bank 13)
for tile→palette mapping. Definitive testing proved this table returns
WRONG values during VBlank - only 54-61% of tilemap positions were
correctly colored, with systematic even/odd position skipping.

Fix: Replace ROM lookup table with INLINE comparison chain (subroutine).
This is the same proven approach used in v2.36 (STABLE), which had no
BG accuracy issues. No ROM reads needed during the BG colorizer loop.

Ordering: BG → Palette → OBJ → DMA (same as v2.36 STABLE)
- BG colorizer runs FIRST: full 4560M VBlank budget for VRAM writes
- Palette registers writable during any LCD mode on CGB (no VBlank needed)
- OBJ colorizer writes WRAM (always accessible)
- DMA runs last (leaves A=0 for bank switch trick)

Timing: 48 tiles × ~90M = 4320M BG < 4560M VBlank
Full sweep: 1024/48 = ~21 frames (~0.35 seconds at 60fps)

INHERITED from v2.45:
- D-pad debounce (2 reads) + A=0 bank switch trick
- Both-buffer shadow OBJ (C000 + C100)
- Multi-boss palette system (8 bosses, table-based)
- Per-entity projectile detection
- Powerup-based Palette 0
- Stage detection via 0xFFD0
- Dual tilemap (0x9800 + 0x9C00) processing
- FFC1 game mode check
- FF91/FF92 counter (confirmed not corrupted by game)
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> dict:
    """Load all palette data from YAML file. Returns dict of named byte arrays."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors: list[str]) -> bytes:
        result = bytearray()
        for c in colors:
            val = int(c, 16) & 0x7FFF
            result.extend([val & 0xFF, (val >> 8) & 0xFF])
        return bytes(result)

    # BG palettes (64 bytes total)
    bg_keys = ['Dungeon', 'BG1', 'BG2', 'BG3', 'BG4', 'BG5', 'BG6', 'BG7']
    bg_data = bytearray()
    for key in bg_keys:
        if key in data.get('bg_palettes', {}):
            bg_data.extend(pal_to_bytes(data['bg_palettes'][key]['colors']))
        else:
            bg_data.extend(pal_to_bytes(["7FFF", "5294", "2108", "0000"]))

    # OBJ palettes (64 bytes total)
    obj_key_map = {
        0: ('EnemyProjectile', ["0000", "7C1F", "5817", "3010"]),
        1: ('SaraDragon', ["0000", "03E0", "01C0", "0000"]),
        2: ('SaraWitch', ["0000", "2EBE", "511F", "0842"]),
        3: ('SaraProjectileAndCrow', ["0000", "001F", "0017", "000F"]),
        4: ('Hornets', ["0000", "03FF", "00DF", "0000"]),
        5: ('OrcGround', ["0000", "02A0", "0160", "0000"]),
        6: ('Humanoid', ["0000", "7C1F", "4C0F", "0000"]),
        7: ('Catfish', ["0000", "7FE0", "3CC0", "0000"]),
    }
    obj_data = bytearray()
    for i in range(8):
        key, fallback = obj_key_map[i]
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(fallback))

    # Boss palette table (8 bosses x 8 bytes = 64 bytes)
    boss_keys = ['Gargoyle', 'Spider', 'Boss3_Crimson', 'Boss4_Ice',
                 'Boss5_Void', 'Boss6_Poison', 'Boss7_Knight', 'Angela']
    boss_data = data.get('boss_palettes', {})
    boss_palette_table = bytearray()
    boss_slot_table = bytearray()
    for key in boss_keys:
        entry = boss_data.get(key, {})
        colors = entry.get('colors', ["0000", "7FFF", "5294", "2108"])
        slot = entry.get('slot', 6)
        boss_palette_table.extend(pal_to_bytes(colors))
        boss_slot_table.append(slot)

    # Jet palettes
    jet_data = data.get('obj_palettes', {})
    sara_witch_jet = pal_to_bytes(jet_data.get('SaraWitchJet', {}).get('colors', ["0000", "7C1F", "5817", "3010"]))
    sara_dragon_jet = pal_to_bytes(jet_data.get('SaraDragonJet', {}).get('colors', ["0000", "7FE0", "4EC0", "2D80"]))

    # Powerup projectile palettes
    powerup_data = data.get('powerup_palettes', {})
    spiral_proj = pal_to_bytes(powerup_data.get('SpiralProjectile', {}).get('colors', ["0000", "7FE0", "5EC0", "3E80"]))
    shield_proj = pal_to_bytes(powerup_data.get('ShieldProjectile', {}).get('colors', ["0000", "03FF", "02BF", "019F"]))
    turbo_proj = pal_to_bytes(powerup_data.get('TurboProjectile', {}).get('colors', ["0000", "00FF", "00BF", "005F"]))

    return {
        'bg_data': bytes(bg_data),
        'obj_data': bytes(obj_data),
        'boss_palette_table': bytes(boss_palette_table),
        'boss_slot_table': bytes(boss_slot_table),
        'sara_witch_jet': sara_witch_jet,
        'sara_dragon_jet': sara_dragon_jet,
        'spiral_proj': spiral_proj,
        'shield_proj': shield_proj,
        'turbo_proj': turbo_proj,
    }


def create_tile_based_colorizer(colorizer_base_addr: int) -> bytes:
    """Tile-based OBJ colorizer with per-entity projectile detection. Unchanged from v2.33."""
    code = bytearray()
    labels = {}
    forward_jumps = []

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def emit_jr(opcode, target_label):
        code.append(opcode)
        forward_jumps.append((len(code), target_label))
        code.append(0x00)

    emit([0x06, 0x28])  # LD B, 40
    labels['loop_start'] = len(code)

    emit([0x3E, 0x28, 0x90, 0xFE, 0x04])  # LD A, 40; SUB B; CP 4
    emit_jr(0x38, 'sara_palette')

    emit([0x2B, 0x7E, 0x23, 0x4F])  # DEC HL; LD A, [HL]; INC HL; LD C, A

    emit([0xFE, 0x10])
    emit_jr(0x30, 'check_higher_tiles')

    emit([0xFE, 0x0F])
    emit_jr(0x28, 'pal_sara_w_proj')
    emit([0xFE, 0x06])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x09])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x0A])
    emit_jr(0x28, 'pal_sara_d_proj')

    emit([0xFE, 0x02])
    emit_jr(0x38, 'pal_enemy_proj')

    emit([0x3E, 0x00])
    emit_jr(0x18, 'apply_palette')

    labels['check_higher_tiles'] = len(code)
    emit([0xFE, 0x20])
    emit_jr(0x30, 'check_sara_sprite')
    emit([0x3E, 0x04])
    emit_jr(0x18, 'apply_palette')

    labels['check_sara_sprite'] = len(code)
    emit([0xFE, 0x30])
    emit_jr(0x38, 'sara_palette')

    emit([0x7B, 0xB7])
    emit_jr(0x20, 'boss_palette')

    emit(0x79)
    emit([0xFE, 0x50])
    emit_jr(0x38, 'check_crow_hornet')
    emit([0xFE, 0x60])
    emit_jr(0x38, 'pal_orc')
    emit([0xFE, 0x70])
    emit_jr(0x38, 'pal_humanoid')
    emit([0xFE, 0x80])
    emit_jr(0x38, 'pal_catfish')
    emit([0x3E, 0x04])
    emit_jr(0x18, 'apply_palette')

    labels['check_crow_hornet'] = len(code)
    emit([0x79, 0xFE, 0x40])
    emit_jr(0x30, 'pal_hornet')
    emit([0x3E, 0x03])
    emit_jr(0x18, 'apply_palette')

    labels['pal_sara_w_proj'] = len(code)
    emit([0x3E, 0x00])
    emit_jr(0x18, 'apply_palette')

    labels['pal_sara_d_proj'] = len(code)
    emit([0x3E, 0x00])
    emit_jr(0x18, 'apply_palette')

    labels['pal_enemy_proj'] = len(code)
    emit([0x3E, 0x03])
    emit_jr(0x18, 'apply_palette')

    labels['pal_hornet'] = len(code)
    emit([0x3E, 0x04])
    emit_jr(0x18, 'apply_palette')

    labels['pal_orc'] = len(code)
    emit([0x3E, 0x05])
    emit_jr(0x18, 'apply_palette')

    labels['pal_humanoid'] = len(code)
    emit([0x3E, 0x06])
    emit_jr(0x18, 'apply_palette')

    labels['pal_catfish'] = len(code)
    emit([0x3E, 0x07])
    emit_jr(0x18, 'apply_palette')

    labels['sara_palette'] = len(code)
    emit(0x7A)
    emit_jr(0x18, 'apply_palette')

    labels['boss_palette'] = len(code)
    emit(0x7B)

    labels['apply_palette'] = len(code)
    emit([0x4F, 0x7E, 0xE6, 0xF8, 0xB1, 0x77])

    emit([0x23, 0x23, 0x23, 0x23, 0x05])
    loop_abs_addr = colorizer_base_addr + labels['loop_start']
    emit([0xC2, loop_abs_addr & 0xFF, (loop_abs_addr >> 8) & 0xFF])
    emit([0xC9])

    for offset_pos, target_label in forward_jumps:
        target = labels[target_label]
        offset = target - (offset_pos + 1)
        if offset < -128 or offset > 127:
            raise ValueError(f"Jump to {target_label} out of range: {offset}")
        code[offset_pos] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int, boss_slot_table_addr: int) -> bytes:
    """Shadow colorizer main - processes BOTH shadow OAM buffers. Unchanged from v2.36."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # Push all registers

    # Read Sara form (0xFFBE) -> D register
    code.extend([0xF0, 0xBE, 0xB7, 0x20, 0x04])
    code.extend([0x16, 0x02, 0x18, 0x02])  # Sara W: LD D, 2; JR +2
    code.extend([0x16, 0x01])  # Sara D: LD D, 1

    # Read boss flag (0xFFBF) -> E register via table lookup
    code.extend([0xF0, 0xBF])
    code.extend([0xB7])
    no_boss_jr_pos = len(code)
    code.extend([0x28, 0x00])

    code.extend([0x3D])
    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])
    code.extend([0x5E])
    done_boss_jr_pos = len(code)
    code.extend([0x18, 0x00])

    no_boss_pos = len(code)
    code[no_boss_jr_pos + 1] = no_boss_pos - (no_boss_jr_pos + 2)
    code.extend([0x1E, 0x00])

    done_boss_pos = len(code)
    code[done_boss_jr_pos + 1] = done_boss_pos - (done_boss_jr_pos + 2)

    # Colorize BOTH buffers
    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1, 0xC9])
    return bytes(code)


def create_palette_loader(
    palette_data_addr: int,
    boss_palette_table_addr: int,
    boss_slot_table_addr: int,
    sara_witch_jet_addr: int,
    sara_dragon_jet_addr: int,
    spiral_proj_addr: int,
    shield_proj_addr: int,
    turbo_proj_addr: int,
) -> bytes:
    """Palette loader - unchanged from v2.33."""
    code = bytearray()

    code.extend([0xF0, 0xD0])
    code.append(0x57)

    # Load BG palettes (64 bytes)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 0 (dynamic: powerup > form)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x3E, 0x80, 0xE0, 0x6A])

    code.extend([0xF0, 0xC0])
    code.extend([0xB7])
    code.extend([0x28, 23])

    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x05])
    code.extend([0x21, spiral_proj_addr & 0xFF, (spiral_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 17])

    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x05])
    code.extend([0x21, shield_proj_addr & 0xFF, (shield_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 8])

    code.extend([0x21, turbo_proj_addr & 0xFF, (turbo_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 3])

    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])

    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # OBJ palette 1
    code.extend([0x3E, 0x88, 0xE0, 0x6A])
    sara_dragon_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_addr & 0xFF, (sara_dragon_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # OBJ palette 2
    code.extend([0x3E, 0x90, 0xE0, 0x6A])
    sara_witch_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_addr & 0xFF, (sara_witch_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # OBJ palettes 3-5
    code.extend([0x3E, 0x98, 0xE0, 0x6A])
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # OBJ palette 6
    code.extend([0x3E, 0xB0, 0xE0, 0x6A])
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # OBJ palette 7
    code.extend([0x3E, 0xB8, 0xE0, 0x6A])
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Boss override
    code.extend([0xF0, 0xBF])
    code.extend([0xB7])
    boss_skip_pos = len(code)
    code.extend([0x28, 0x00])

    code.extend([0x3D])
    code.extend([0x5F])

    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])
    code.extend([0x7E])

    code.extend([0x87])
    code.extend([0xF6, 0x80])
    code.extend([0xE0, 0x6A])

    code.extend([0x7B])
    code.extend([0x87])
    code.extend([0x87])
    code.extend([0x87])
    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_palette_table_addr & 0xFF, (boss_palette_table_addr >> 8) & 0xFF])
    code.extend([0x09])

    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    no_boss_pos = len(code)
    code[boss_skip_pos + 1] = no_boss_pos - (boss_skip_pos + 2)

    code.append(0xC9)
    return bytes(code)


def create_tile_to_palette_subroutine() -> bytes:
    """Inline tile→palette subroutine. No ROM reads needed.

    Input: A = tile ID
    Output: A = palette number (0, 1, or 6)
    Clobbers: flags

    Tile classification:
      0x00-0x04 → palette 0  (floor checkerboard)
      0x05-0x06 → palette 6  (platform corners)
      0x07-0x12 → palette 0  (floor edges)
      0x13-0x5F → palette 6  (structural + platforms + walls)
      0x60-0x87 → palette 0  (arch/doorway/UI)
      0x88-0xDF → palette 1  (items - gold)
      0xE0-0xFD → palette 6  (decorative/structural)
      0xFE-0xFF → palette 0  (void)
    """
    code = bytearray()
    # We'll build the comparison chain and fix up jumps after

    # CP 0x05; JR C, pal0   (tiles 0x00-0x04)
    cp1 = len(code)
    code.extend([0xFE, 0x05, 0x38, 0x00])

    # CP 0x07; JR C, pal6   (tiles 0x05-0x06)
    cp2 = len(code)
    code.extend([0xFE, 0x07, 0x38, 0x00])

    # CP 0x13; JR C, pal0   (tiles 0x07-0x12)
    cp3 = len(code)
    code.extend([0xFE, 0x13, 0x38, 0x00])

    # CP 0x60; JR C, pal6   (tiles 0x13-0x5F)
    cp4 = len(code)
    code.extend([0xFE, 0x60, 0x38, 0x00])

    # CP 0x88; JR C, pal0   (tiles 0x60-0x87)
    cp5 = len(code)
    code.extend([0xFE, 0x88, 0x38, 0x00])

    # CP 0xE0; JR C, pal1   (tiles 0x88-0xDF)
    cp6 = len(code)
    code.extend([0xFE, 0xE0, 0x38, 0x00])

    # CP 0xFE; JR C, pal6   (tiles 0xE0-0xFD)
    cp7 = len(code)
    code.extend([0xFE, 0xFE, 0x38, 0x00])

    # Fall through: 0xFE-0xFF → palette 0
    pal0 = len(code)
    code.extend([0xAF, 0xC9])          # XOR A; RET  (A=0, 2 bytes)

    pal1 = len(code)
    code.extend([0x3E, 0x01, 0xC9])    # LD A, 1; RET (3 bytes)

    pal6 = len(code)
    code.extend([0x3E, 0x06, 0xC9])    # LD A, 6; RET (3 bytes)

    # Fix up JR offsets
    code[cp1 + 3] = (pal0 - (cp1 + 4)) & 0xFF
    code[cp2 + 3] = (pal6 - (cp2 + 4)) & 0xFF
    code[cp3 + 3] = (pal0 - (cp3 + 4)) & 0xFF
    code[cp4 + 3] = (pal6 - (cp4 + 4)) & 0xFF
    code[cp5 + 3] = (pal0 - (cp5 + 4)) & 0xFF
    code[cp6 + 3] = (pal1 - (cp6 + 4)) & 0xFF
    code[cp7 + 3] = (pal6 - (cp7 + 4)) & 0xFF

    return bytes(code)


def create_bg_colorizer_inline(tile_to_pal_addr: int) -> bytes:
    """BG colorizer with inline tile→palette subroutine (no ROM lookup table).

    Runs FIRST in VBlank - has full 4560M budget for VRAM reads/writes.
    48 tiles × ~90M = 4320M < 4560M VBlank (avg, depends on tile mix).
    Full sweep: 1024/48 = ~21 frames (~0.35 seconds at 60fps).

    HRAM: FF91=counter low, FF92=counter high (confirmed unused by game).
    Uses FFEE as temp storage for palette A during loop (confirmed unused by game).
    """
    TILES_PER_VBLANK = 48

    code = bytearray()

    # === CHECK GAME MODE ===
    code.extend([0xF0, 0xC1])        # LDH A, [FFC1]
    code.extend([0xB7])              # OR A
    code.extend([0xC8])              # RET Z (skip on menus)

    code.extend([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL

    # === LOAD SWEEP POSITION (FF91=low, FF92=high) ===
    code.extend([0xF0, 0x91])        # LDH A, [FF91]   ; counter low
    code.extend([0x5F])              # LD E, A
    code.extend([0xF0, 0x92])        # LDH A, [FF92]   ; counter high
    code.extend([0xE6, 0x03])        # AND 0x03         ; safety mask (0-3)
    code.extend([0xC6, 0x98])        # ADD A, 0x98      ; + tilemap base
    code.extend([0x57])              # LD D, A          ; DE = 0x9800 + offset

    # Set tile count
    code.extend([0x06, TILES_PER_VBLANK])  # LD B, 44

    # Ensure VRAM bank 0 before loop
    code.extend([0xAF])              # XOR A            ; 1M
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A    ; 3M -> VRAM bank 0

    # === SWEEP LOOP ===
    sweep_start = len(code)

    # --- Step 1: Read tile A from tilemap A (0x9800 range, bank 0) ---
    code.extend([0x1A])              # LD A, [DE]        ; 2M -> tile ID from 0x9800

    # --- Step 2: Lookup palette A via subroutine ---
    code.extend([0xCD, tile_to_pal_addr & 0xFF, (tile_to_pal_addr >> 8) & 0xFF])
    # Returns: A = palette A

    # --- Step 3: Save palette A to HRAM temp ---
    code.extend([0xE0, 0xEE])        # LDH [FFEE], A    ; 3M -> save palette A

    # --- Step 4: Read tile B from tilemap B (0x9C00 range, bank 0) ---
    code.extend([0x7A])              # LD A, D           ; 1M
    code.extend([0xEE, 0x04])        # XOR 0x04          ; 2M -> 0x98->0x9C
    code.extend([0x67])              # LD H, A           ; 1M
    code.extend([0x6B])              # LD L, E           ; 1M
    code.extend([0x7E])              # LD A, [HL]        ; 2M -> tile ID from 0x9C00

    # --- Step 5: Lookup palette B via subroutine ---
    code.extend([0xCD, tile_to_pal_addr & 0xFF, (tile_to_pal_addr >> 8) & 0xFF])
    # Returns: A = palette B
    code.extend([0x4F])              # LD C, A           ; 1M -> C = palette B

    # --- Step 6: Switch to VRAM bank 1 ---
    code.extend([0x3E, 0x01])        # LD A, 1           ; 2M
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A     ; 3M -> VRAM bank 1

    # --- Step 7: Write palette B to tilemap B (HL still = 0x9C00+pos) ---
    code.extend([0x71])              # LD [HL], C        ; 2M -> write palette B

    # --- Step 8: Write palette A to tilemap A ---
    code.extend([0x62])              # LD H, D           ; 1M
    code.extend([0x6B])              # LD L, E           ; 1M
    code.extend([0xF0, 0xEE])        # LDH A, [FFEE]     ; 3M -> palette A
    code.extend([0x77])              # LD [HL], A        ; 2M -> write palette A to 0x9800

    # --- Step 9: Switch back to VRAM bank 0 ---
    code.extend([0xAF])              # XOR A             ; 1M
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A     ; 3M -> bank 0

    # --- Step 10: Advance position ---
    code.extend([0x13])              # INC DE            ; 2M

    # Wrap: if D >= 0x9C, reset to 0x98
    code.extend([0x7A])              # LD A, D           ; 1M
    code.extend([0xFE, 0x9C])        # CP 0x9C           ; 2M
    code.extend([0x38, 0x02])        # JR C, +2          ; 3M (no wrap)
    code.extend([0x16, 0x98])        # LD D, 0x98        ; 2M (wrap)

    # --- Step 11: Loop ---
    code.extend([0x05])              # DEC B             ; 1M
    sweep_end = len(code)
    sweep_offset = sweep_start - (sweep_end + 2)
    if sweep_offset < -128:
        raise ValueError(f"Sweep loop JR offset {sweep_offset} out of range! Loop body too large.")
    code.extend([0x20, sweep_offset & 0xFF])  # JR NZ, sweep_loop ; 3M

    # === SAVE POSITION COUNTER (FF91=low, FF92=high) ===
    code.extend([0x7A])              # LD A, D
    code.extend([0xD6, 0x98])        # SUB 0x98          ; relative high (0-3)
    code.extend([0xE6, 0x03])        # AND 0x03          ; safety mask
    code.extend([0xE0, 0x92])        # LDH [FF92], A
    code.extend([0x7B])              # LD A, E
    code.extend([0xE0, 0x91])        # LDH [FF91], A

    # === CLEANUP: ensure VRAM bank 0 ===
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A     ; guarantee bank 0 on exit

    code.extend([0xE1, 0xD1, 0xC1])  # POP HL, DE, BC
    code.extend([0xC9])              # RET

    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function: bg_colorizer -> palette_loader -> shadow_main -> DMA.

    v2.46: BG colorizer runs FIRST (like v2.36 STABLE) to guarantee all VRAM
    writes complete within VBlank. Palette registers are writable during any
    LCD mode on CGB, so palette loader doesn't need VBlank.

    Order rationale:
    1. BG colorizer (44x95M=4180M) - MUST be in VBlank for VRAM writes
    2. Palette loader (~1400M) - safe outside VBlank (palette regs always writable)
    3. Shadow OBJ colorizer (~800M) - writes WRAM, safe outside VBlank
    4. DMA (160M) - copies shadow OAM to hardware
       DMA is LAST - leaves A=0 on return (used by hook for bank switch)
    """
    code = bytearray()
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF, 0xC9])
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook with debounced input handling. Same as v2.45."""
    lo = combined_func_addr & 0xFF
    hi = (combined_func_addr >> 8) & 0xFF

    joypad_input = bytearray([
        # D-pad with 2 reads for debounce (14 bytes)
        0x3E, 0x20,        # LD A, 0x20        ; select d-pad
        0xE0, 0x00,        # LDH [FF00], A
        0xF0, 0x00,        # LDH A, [FF00]     ; 1st read (discard - pullup settle)
        0xF0, 0x00,        # LDH A, [FF00]     ; 2nd read (keep - stable value)
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xCB, 0x37,        # SWAP A
        0x47,              # LD B, A
        # Buttons via loop: 8 reads (11 bytes)
        0x3E, 0x10,        # LD A, 0x10        ; select buttons
        0xE0, 0x00,        # LDH [FF00], A
        0x0E, 0x08,        # LD C, 8
        0xF0, 0x00,        # .loop: LDH A,[FF00]
        0x0D,              # DEC C
        0x20, 0xFB,        # JR NZ, .loop
        # Combine + deselect (10 bytes)
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xB0,              # OR B
        0xE0, 0x93,        # LDH [FF93], A
        0x3E, 0x30,        # LD A, 0x30
        0xE0, 0x00,        # LDH [FF00], A     ; deselect
    ])  # 14 + 11 + 10 = 35 bytes

    hook_code = bytearray([
        0x3E, 0x0D,              # LD A, 0x0D       ; bank 13
        0xEA, 0x00, 0x20,        # LD [0x2000], A   ; switch to bank 13
        0xCD, lo, hi,            # CALL combined
        0xEA, 0x00, 0x20,        # LD [0x2000], A   ; A=0 from DMA -> bank 0 = bank 1 (MBC1)
        0xC9,                    # RET
    ])  # 12 bytes

    total = joypad_input + hook_code
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be exactly 47!"
    return bytes(total)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.46 ===")
    print("Fix BG Colorizer - Inline Comparison (No ROM Lookup)")
    print()
    print("ROOT CAUSE: v2.44/v2.45 ROM lookup table at 0x6B00 returned wrong")
    print("values during VBlank. Only 54-61% of tilemap positions were colored.")
    print()
    print("Fix: Inline tile→palette comparison subroutine (no ROM reads).")
    print("Same proven approach as v2.36 (STABLE).")
    print()
    print("Changes from v2.45:")
    print("  1. BG colorizer: inline comparison subroutine (no ROM lookup table)")
    print("  2. Combined order: BG → Palette → OBJ → DMA (BG-first, like v2.36)")
    print("  3. 48 tiles/frame × ~90M = 4320M < 4560M VBlank budget")
    print("  4. Full sweep in ~21 frames (0.35 seconds)")
    print()

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)

    palettes = load_palettes_from_yaml(palette_yaml)

    # === DATA LAYOUT (Bank 13) ===
    palette_data_addr = 0x6800
    boss_palette_table_addr = 0x6880
    boss_slot_table_addr = 0x68C0
    sara_witch_jet_addr = 0x68D0
    sara_dragon_jet_addr = 0x68D8
    spiral_proj_addr = 0x68E0
    shield_proj_addr = 0x68E8
    turbo_proj_addr = 0x68F0

    # === CODE LAYOUT (Bank 13) ===
    palette_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    # v2.46: No lookup table needed! Replaced by subroutine.
    tile_to_pal_addr = 0x6B00        # Tile→palette subroutine (36 bytes)
    bg_colorizer_addr = 0x6C00       # BG colorizer (calls subroutine)
    combined_addr = 0x6D00           # Combined function

    # Generate code
    palette_loader = create_palette_loader(
        palette_data_addr, boss_palette_table_addr, boss_slot_table_addr,
        sara_witch_jet_addr, sara_dragon_jet_addr,
        spiral_proj_addr, shield_proj_addr, turbo_proj_addr,
    )
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_table_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_to_pal = create_tile_to_palette_subroutine()
    bg_colorizer = create_bg_colorizer_inline(tile_to_pal_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    # Print sizes
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X} (ends 0x{palette_loader_addr + len(palette_loader):04X})")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X} (ends 0x{shadow_main_addr + len(shadow_main):04X})")
    print(f"OBJ colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X} (ends 0x{colorizer_addr + len(colorizer):04X})")
    print(f"Tile→Palette sub: {len(tile_to_pal)} bytes at 0x{tile_to_pal_addr:04X} (ends 0x{tile_to_pal_addr + len(tile_to_pal):04X})")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X} (ends 0x{bg_colorizer_addr + len(bg_colorizer):04X})")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"VBlank hook: {len(vblank_hook)} bytes at 0x0824")

    # Verify no overlaps
    regions = [
        ('palette_loader', palette_loader_addr, len(palette_loader)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_to_pal', tile_to_pal_addr, len(tile_to_pal)),
        ('bg_colorizer', bg_colorizer_addr, len(bg_colorizer)),
        ('combined', combined_addr, len(combined)),
    ]
    for i, (name_a, start_a, size_a) in enumerate(regions):
        for name_b, start_b, size_b in regions[i+1:]:
            end_a = start_a + size_a
            end_b = start_b + size_b
            if start_a < end_b and start_b < end_a:
                raise ValueError(f"OVERLAP: {name_a} (0x{start_a:04X}-0x{end_a:04X}) "
                                 f"and {name_b} (0x{start_b:04X}-0x{end_b:04X})")

    bank13_offset = 13 * 0x4000

    def write_bank13(addr, data):
        rom_offset = bank13_offset + (addr - 0x4000)
        rom[rom_offset:rom_offset + len(data)] = data

    # Write palette data
    write_bank13(palette_data_addr, palettes['bg_data'])
    write_bank13(palette_data_addr + 64, palettes['obj_data'])
    write_bank13(boss_palette_table_addr, palettes['boss_palette_table'])
    write_bank13(boss_slot_table_addr, palettes['boss_slot_table'])
    write_bank13(sara_witch_jet_addr, palettes['sara_witch_jet'])
    write_bank13(sara_dragon_jet_addr, palettes['sara_dragon_jet'])
    write_bank13(spiral_proj_addr, palettes['spiral_proj'])
    write_bank13(shield_proj_addr, palettes['shield_proj'])
    write_bank13(turbo_proj_addr, palettes['turbo_proj'])

    # Write code
    write_bank13(palette_loader_addr, palette_loader)
    write_bank13(shadow_main_addr, shadow_main)
    write_bank13(colorizer_addr, colorizer)
    write_bank13(tile_to_pal_addr, tile_to_pal)
    write_bank13(bg_colorizer_addr, bg_colorizer)
    write_bank13(combined_addr, combined)

    # Patch original ROM hooks
    rom[0x06D5:0x06D5 + 3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print(f"\nSet CGB flag at 0x143")

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom)

    print(f"\nROM patched successfully")
    print(f"  Output: {output_rom}")
    print(f"\nTest with:")
    print(f"  ./mgba-qt.sh {output_rom} -t save_states_for_claude/v2.31_sara_w_mid_level1.ss0")


if __name__ == "__main__":
    main()
