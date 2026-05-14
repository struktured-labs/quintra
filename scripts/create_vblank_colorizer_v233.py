#!/usr/bin/env python3
"""
v2.33: Multi-Boss Palette System + Turbo Powerup

NEW FEATURES (Phase 2 - Multi-Boss):
- Table-based boss palette system supporting 8 distinct bosses
- Boss palette lookup table: 8 bosses x 8 bytes = 64 bytes
- Boss slot table: 8 bytes mapping boss_flag -> target palette slot (6 or 7)
- Boss flag values 1-8 each load unique colors into their target slot
- Palette loader uses table indexing instead of hardcoded checks

NEW FEATURES (Phase 4 - Turbo Powerup):
- Added 0xFFC0=3: Turbo powerup -> orange projectile palette
- Extended powerup check chain: spiral(1) -> shield(2) -> turbo(3)

BOSS ASSIGNMENTS:
  boss_flag=1: Gargoyle -> Palette 6 (dark magenta)
  boss_flag=2: Spider -> Palette 7 (red/orange)
  boss_flag=3: Crimson -> Palette 6 (crimson/blood)
  boss_flag=4: Ice -> Palette 7 (frost blue)
  boss_flag=5: Void -> Palette 6 (dark violet)
  boss_flag=6: Poison -> Palette 7 (toxic green)
  boss_flag=7: Knight -> Palette 6 (gold/bronze)
  boss_flag=8: Angela -> Palette 7 (white/silver)

INHERITED from v2.32:
- Per-entity projectile tile detection
- Powerup-based Palette 0 (spiral=cyan, shield=gold)
- Stage detection via 0xFFD0
- BG item colorization
- Flicker-free pre-DMA shadow buffer modification
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
    obj_keys = ['SaraProjectileWitch', 'SaraDragon', 'SaraWitch', 'Crow',
                'Hornets', 'OrcGround', 'Humanoid', 'Catfish']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            if key == 'SaraProjectileWitch':
                obj_data.extend(pal_to_bytes(["0000", "7C1F", "5817", "3010"]))
            else:
                obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

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
    """
    Tile-based colorizer with per-entity projectile detection.
    Unchanged from v2.32 - the tile colorizer doesn't need boss system changes.

    Uses D register (Sara palette) and E register (boss palette slot).
    When E != 0, all enemies (tiles >= 0x30) get palette E.
    """
    code = bytearray()
    labels = {}
    forward_jumps = []

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def emit_jr(opcode, target_label):
        code.append(opcode)
        forward_jumps.append((len(code), target_label))
        code.append(0x00)

    # === MAIN LOOP ===
    emit([0x06, 0x28])  # LD B, 40
    labels['loop_start'] = len(code)

    # Check if Sara slot (0-3)
    emit([0x3E, 0x28, 0x90, 0xFE, 0x04])  # LD A, 40; SUB B; CP 4
    emit_jr(0x38, 'sara_palette')

    # Read tile into C
    emit([0x2B, 0x7E, 0x23, 0x4F])  # DEC HL; LD A, [HL]; INC HL; LD C, A

    # === PROJECTILE CHECK (tiles 0x00-0x0F) ===
    emit([0xFE, 0x10])  # CP 0x10
    emit_jr(0x30, 'check_higher_tiles')

    # Tile 0x0F = Sara W projectile
    emit([0xFE, 0x0F])
    emit_jr(0x28, 'pal_sara_w_proj')

    # Tiles 0x06, 0x09, 0x0A = Sara D projectile
    emit([0xFE, 0x06])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x09])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x0A])
    emit_jr(0x28, 'pal_sara_d_proj')

    # Tiles 0x00-0x01 = enemy projectile
    emit([0xFE, 0x02])
    emit_jr(0x38, 'pal_enemy_proj')

    # Default projectile palette (0x02-0x05, 0x07-0x08, 0x0B-0x0E)
    emit([0x3E, 0x00])  # LD A, 0
    emit_jr(0x18, 'apply_palette')

    # === HIGHER TILE CHECKS (0x10+) ===
    labels['check_higher_tiles'] = len(code)
    emit([0xFE, 0x20])
    emit_jr(0x30, 'check_sara_sprite')
    emit([0x3E, 0x04])  # Effects palette
    emit_jr(0x18, 'apply_palette')

    labels['check_sara_sprite'] = len(code)
    emit([0xFE, 0x30])
    emit_jr(0x38, 'sara_palette')

    # Check boss mode
    emit([0x7B, 0xB7])  # LD A, E; OR A
    emit_jr(0x20, 'boss_palette')

    # === ENEMY TILE RANGES ===
    emit(0x79)  # LD A, C
    emit([0xFE, 0x50])
    emit_jr(0x38, 'check_crow_hornet')
    emit([0xFE, 0x60])
    emit_jr(0x38, 'pal_orc')
    emit([0xFE, 0x70])
    emit_jr(0x38, 'pal_humanoid')
    emit([0xFE, 0x80])
    emit_jr(0x38, 'pal_catfish')
    emit([0x3E, 0x04])  # Default palette
    emit_jr(0x18, 'apply_palette')

    # === SUB-CHECKS ===
    labels['check_crow_hornet'] = len(code)
    emit([0x79, 0xFE, 0x40])
    emit_jr(0x30, 'pal_hornet')
    emit([0x3E, 0x03])  # Crow
    emit_jr(0x18, 'apply_palette')

    # === PALETTE HANDLERS ===
    labels['pal_sara_w_proj'] = len(code)
    emit([0x3E, 0x00])  # Palette 0
    emit_jr(0x18, 'apply_palette')

    labels['pal_sara_d_proj'] = len(code)
    emit([0x3E, 0x00])  # Palette 0
    emit_jr(0x18, 'apply_palette')

    labels['pal_enemy_proj'] = len(code)
    emit([0x3E, 0x03])  # Palette 3
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
    emit(0x7A)  # LD A, D
    emit_jr(0x18, 'apply_palette')

    labels['boss_palette'] = len(code)
    emit(0x7B)  # LD A, E (boss palette slot number from table)
    # Fall through to apply_palette

    # === APPLY PALETTE ===
    labels['apply_palette'] = len(code)
    emit([0x4F, 0x7E, 0xE6, 0xF8, 0xB1, 0x77])  # LD C,A; LD A,[HL]; AND F8; OR C; LD [HL],A

    # Next sprite
    emit([0x23, 0x23, 0x23, 0x23, 0x05])  # INC HL x4; DEC B
    loop_abs_addr = colorizer_base_addr + labels['loop_start']
    emit([0xC2, loop_abs_addr & 0xFF, (loop_abs_addr >> 8) & 0xFF])  # JP NZ
    emit([0xC9])  # RET

    # === FIX ALL FORWARD JUMPS ===
    for offset_pos, target_label in forward_jumps:
        target = labels[target_label]
        offset = target - (offset_pos + 1)
        if offset < -128 or offset > 127:
            raise ValueError(f"Jump to {target_label} out of range: {offset}")
        code[offset_pos] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int, boss_slot_table_addr: int) -> bytes:
    """
    Shadow colorizer main - sets up D and E registers for colorizer.

    v2.33: Uses boss_slot_table for E register lookup instead of hardcoded values.
    D = Sara palette (1=Dragon, 2=Witch)
    E = 0 (no boss) or palette slot from boss_slot_table (6 or 7)
    """
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # Push all registers

    # Read Sara form (0xFFBE) -> D register
    code.extend([0xF0, 0xBE, 0xB7, 0x20, 0x04])  # LDH A,[FFBE]; OR A; JR NZ,+4
    code.extend([0x16, 0x02, 0x18, 0x02])  # Sara W: LD D, 2; JR +2
    code.extend([0x16, 0x01])  # Sara D: LD D, 1

    # Read boss flag (0xFFBF) -> E register via table lookup
    code.extend([0xF0, 0xBF])  # LDH A, [0xFFBF]
    code.extend([0xB7])  # OR A
    # JR Z, no_boss - calculate offset after emitting boss lookup code
    no_boss_jr_pos = len(code)
    code.extend([0x28, 0x00])  # placeholder

    # Boss active: look up slot from table
    code.extend([0x3D])  # DEC A (0-based index)
    code.extend([0x4F])  # LD C, A
    code.extend([0x06, 0x00])  # LD B, 0
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])  # ADD HL, BC
    code.extend([0x5E])  # LD E, [HL]
    done_boss_jr_pos = len(code)
    code.extend([0x18, 0x00])  # JR done_boss (placeholder)

    # no_boss:
    no_boss_pos = len(code)
    code[no_boss_jr_pos + 1] = no_boss_pos - (no_boss_jr_pos + 2)
    code.extend([0x1E, 0x00])  # LD E, 0

    # done_boss:
    done_boss_pos = len(code)
    code[done_boss_jr_pos + 1] = done_boss_pos - (done_boss_jr_pos + 2)

    # Call colorizer for both shadow buffers
    code.extend([0x21, 0x03, 0xC0])  # LD HL, 0xC003
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])  # LD HL, 0xC103
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1, 0xC9])  # Pop all and return
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
    """
    Load CGB palettes with multi-boss table system + turbo powerup (v2.33).

    Flow:
    1. Load BG palettes (64 bytes)
    2. Load OBJ palette 0 (dynamic: form-based or powerup-based)
    3. Load OBJ palettes 1-2 (Sara with jet form variants)
    4. Load OBJ palettes 3-5 (Crow, Hornets, Orc)
    5. Load OBJ palette 6 (Humanoid default)
    6. Load OBJ palette 7 (Catfish default)
    7. Boss override: if boss_flag != 0, overwrite target slot from table
    """
    code = bytearray()

    # Save stage flag in D register for jet form checks
    code.extend([0xF0, 0xD0])  # LDH A, [0xFFD0]
    code.append(0x57)  # LD D, A

    # === Load BG palettes (64 bytes) ===
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])  # BCPS=0x80, C=64
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])  # Loop

    # === Load OBJ palette 0 (dynamic: powerup > form) ===
    obj_data_addr = palette_data_addr + 64
    code.extend([0x3E, 0x80, 0xE0, 0x6A])  # OCPS = palette 0, auto-increment

    # Check powerup state at 0xFFC0
    code.extend([0xF0, 0xC0])  # LDH A, [0xFFC0]
    code.extend([0xB7])  # OR A
    code.extend([0x28, 23])  # JR Z, no_powerup (skip 23 bytes to no_powerup)

    # Powerup active - check which type
    # Check spiral (0xFFC0 == 1)
    code.extend([0xFE, 0x01])  # CP 1
    code.extend([0x20, 0x05])  # JR NZ, check_shield (+5 bytes)
    code.extend([0x21, spiral_proj_addr & 0xFF, (spiral_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 17])  # JR load_pal0 (+17 bytes)

    # check_shield: (0xFFC0 == 2)
    code.extend([0xFE, 0x02])  # CP 2
    code.extend([0x20, 0x05])  # JR NZ, check_turbo (+5 bytes)
    code.extend([0x21, shield_proj_addr & 0xFF, (shield_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 8])  # JR load_pal0 (+8 bytes)

    # check_turbo: (0xFFC0 == 3 or any other powerup)
    code.extend([0x21, turbo_proj_addr & 0xFF, (turbo_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 3])  # JR load_pal0 (+3 bytes)

    # no_powerup: Load default Sara W projectile palette
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])

    # load_pal0: Load 8 bytes of palette 0
    code.extend([0x0E, 0x08])  # LD C, 8
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])  # Loop

    # === Load OBJ palette 1 (Sara Dragon / Jet form) ===
    code.extend([0x3E, 0x88, 0xE0, 0x6A])  # OCPS = 0x88 (palette 1)
    sara_dragon_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_addr & 0xFF, (sara_dragon_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])  # If stage == 1 (bonus)
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # === Load OBJ palette 2 (Sara Witch / Jet form) ===
    code.extend([0x3E, 0x90, 0xE0, 0x6A])  # OCPS = 0x90 (palette 2)
    sara_witch_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_addr & 0xFF, (sara_witch_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])  # If stage == 1 (bonus)
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # === Load OBJ palettes 3-5 (Crow, Hornets, Orc) ===
    code.extend([0x3E, 0x98, 0xE0, 0x6A])  # OCPS = 0x98 (palette 3)
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])  # LD C, 24 (3 palettes x 8 bytes)
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # === Load OBJ palette 6 (Humanoid - always load default) ===
    code.extend([0x3E, 0xB0, 0xE0, 0x6A])  # OCPS = 0xB0 (palette 6)
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # === Load OBJ palette 7 (Catfish - always load default) ===
    code.extend([0x3E, 0xB8, 0xE0, 0x6A])  # OCPS = 0xB8 (palette 7)
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # === BOSS OVERRIDE (table-based) ===
    # If boss_flag != 0, look up boss palette and target slot from tables,
    # then overwrite the target palette slot with boss-specific colors.
    code.extend([0xF0, 0xBF])  # LDH A, [0xFFBF]
    code.extend([0xB7])  # OR A
    boss_skip_pos = len(code)
    code.extend([0x28, 0x00])  # JR Z, no_boss (placeholder offset)

    # A = boss_flag (1-8), convert to 0-based index
    code.extend([0x3D])  # DEC A
    code.extend([0x5F])  # LD E, A (save index in E)

    # Look up target slot: boss_slot_table[index]
    code.extend([0x4F])  # LD C, A
    code.extend([0x06, 0x00])  # LD B, 0
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])  # ADD HL, BC
    code.extend([0x7E])  # LD A, [HL] -> slot number (6 or 7)

    # Calculate OCPS value: slot * 8 | 0x80
    code.extend([0x87])  # ADD A, A (*2)
    code.extend([0x87])  # ADD A, A (*4)
    code.extend([0x87])  # ADD A, A (*8)
    code.extend([0xF6, 0x80])  # OR 0x80 (auto-increment)
    code.extend([0xE0, 0x6A])  # LDH [OCPS], A

    # Look up boss palette: boss_palette_table[index * 8]
    code.extend([0x7B])  # LD A, E (restore index)
    code.extend([0x87])  # ADD A, A (*2)
    code.extend([0x87])  # ADD A, A (*4)
    code.extend([0x87])  # ADD A, A (*8)
    code.extend([0x4F])  # LD C, A
    code.extend([0x06, 0x00])  # LD B, 0
    code.extend([0x21, boss_palette_table_addr & 0xFF, (boss_palette_table_addr >> 8) & 0xFF])
    code.extend([0x09])  # ADD HL, BC

    # Load 8 bytes of boss palette
    code.extend([0x0E, 0x08])  # LD C, 8
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])  # Loop

    # no_boss: (fix JR offset)
    no_boss_pos = len(code)
    code[boss_skip_pos + 1] = no_boss_pos - (boss_skip_pos + 2)

    code.append(0xC9)  # RET
    return bytes(code)


def create_tile_palette_lookup() -> bytes:
    """256-byte lookup table: tile_id -> BG palette."""
    lookup = bytearray(256)
    for i in range(256):
        if i < 0x20:
            lookup[i] = 0
        elif i < 0x80:
            lookup[i] = 2
        elif i < 0xE0:
            lookup[i] = 1  # Item tiles get gold palette
        elif i == 0xFF:
            lookup[i] = 0
        else:
            lookup[i] = 2
    return bytes(lookup)


def create_bg_colorizer_oneshot(lookup_table_addr: int) -> bytes:
    """One-shot BG colorizer (unchanged from v2.32)."""
    code = bytearray()
    code.extend([0xF0, 0xE0, 0xFE, 0x12, 0xD0])  # Check if all rows done
    code.extend([0xC5, 0xD5, 0x6F, 0x26, 0x00])
    code.extend([0x29, 0x29, 0x29, 0x29, 0x29])  # HL = row * 32
    code.extend([0x01, 0x00, 0x98, 0x09, 0x06, 0x20])

    tile_loop_start = len(code)
    code.extend([0xAF, 0xE0, 0x4F, 0x56])
    code.extend([0xE5, 0x26, (lookup_table_addr >> 8) & 0xFF])
    code.extend([0x7A, 0x6F, 0x5E, 0xE1])
    code.extend([0x3E, 0x01, 0xE0, 0x4F, 0x73])
    code.extend([0x23, 0x05])
    tile_offset = tile_loop_start - len(code) - 2
    code.extend([0x20, tile_offset & 0xFF])

    code.extend([0xD1, 0xC1])
    code.extend([0xF0, 0xE0, 0xC6, 0x01, 0xE0, 0xE0])
    code.extend([0xAF, 0xE0, 0x4F, 0xC9])
    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function that calls all colorization routines."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF, 0xC9])  # Call DMA and return
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook with input handling (matches v2.32 stable)."""
    simplified_input = bytearray([
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
    ])
    hook_code = bytearray([
        0x3E, 0x0D, 0xEA, 0x00, 0x20,  # Switch to bank 13
        0xCD, combined_func_addr & 0xFF, combined_func_addr >> 8,
        0x3E, 0x01, 0xEA, 0x00, 0x20,  # Switch back to bank 1
        0xC9,
    ])
    return bytes(simplified_input + hook_code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.33 ===")
    print("Multi-Boss Palette System + Turbo Powerup")
    print()
    print("NEW in v2.33:")
    print("  Phase 2 - Multi-Boss (8 bosses with table-based lookup):")
    print("    boss_flag=1: Gargoyle (slot 6, dark magenta)")
    print("    boss_flag=2: Spider (slot 7, red/orange)")
    print("    boss_flag=3: Crimson (slot 6, crimson)")
    print("    boss_flag=4: Ice (slot 7, frost blue)")
    print("    boss_flag=5: Void (slot 6, violet)")
    print("    boss_flag=6: Poison (slot 7, toxic green)")
    print("    boss_flag=7: Knight (slot 6, gold)")
    print("    boss_flag=8: Angela (slot 7, white/silver)")
    print("  Phase 4 - Turbo Powerup:")
    print("    0xFFC0=3: Turbo -> orange projectiles")
    print()

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)

    palettes = load_palettes_from_yaml(palette_yaml)

    # === DATA LAYOUT (Bank 13) ===
    palette_data_addr = 0x6800         # 128 bytes (64 BG + 64 OBJ)
    boss_palette_table_addr = 0x6880   # 64 bytes (8 bosses x 8 bytes)
    boss_slot_table_addr = 0x68C0      # 8 bytes (palette slot per boss)
    sara_witch_jet_addr = 0x68D0       # 8 bytes
    sara_dragon_jet_addr = 0x68D8      # 8 bytes
    spiral_proj_addr = 0x68E0          # 8 bytes
    shield_proj_addr = 0x68E8          # 8 bytes
    turbo_proj_addr = 0x68F0           # 8 bytes
    # Data ends at 0x68F8

    # === CODE LAYOUT (Bank 13) ===
    palette_loader_addr = 0x6900       # ~194 bytes -> ends ~0x69C2
    shadow_main_addr = 0x69D0          # ~50 bytes -> ends ~0x6A02
    colorizer_addr = 0x6A10            # ~134 bytes -> ends ~0x6A96
    lookup_table_addr = 0x6B00         # 256 bytes -> ends 0x6BFF
    bg_colorizer_addr = 0x6C00         # ~53 bytes -> ends ~0x6C35
    combined_addr = 0x6D00             # ~16 bytes

    # Generate code
    palette_loader = create_palette_loader(
        palette_data_addr,
        boss_palette_table_addr,
        boss_slot_table_addr,
        sara_witch_jet_addr,
        sara_dragon_jet_addr,
        spiral_proj_addr,
        shield_proj_addr,
        turbo_proj_addr,
    )
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_table_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    lookup_table = create_tile_palette_lookup()
    bg_colorizer = create_bg_colorizer_oneshot(lookup_table_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    # Verify sizes don't overlap
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X} (ends 0x{palette_loader_addr + len(palette_loader):04X})")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X} (ends 0x{shadow_main_addr + len(shadow_main):04X})")
    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X} (ends 0x{colorizer_addr + len(colorizer):04X})")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X} (ends 0x{bg_colorizer_addr + len(bg_colorizer):04X})")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Verify no overlaps
    regions = [
        ('palette_loader', palette_loader_addr, len(palette_loader)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('lookup_table', lookup_table_addr, len(lookup_table)),
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
    write_bank13(lookup_table_addr, lookup_table)
    write_bank13(bg_colorizer_addr, bg_colorizer)
    write_bank13(combined_addr, combined)

    # Patch original ROM hooks
    rom[0x06D5:0x06D5 + 3] = bytearray([0x00, 0x00, 0x00])  # NOP out original
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print("\nSet CGB flag at 0x143")

    # Verify boss palette and slot table data
    print(f"\nBoss palette table ({len(palettes['boss_palette_table'])} bytes):")
    for i in range(8):
        pal = palettes['boss_palette_table'][i*8:(i+1)*8]
        slot = palettes['boss_slot_table'][i]
        print(f"  Boss {i+1}: slot={slot}, data={pal.hex()}")

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom)

    print(f"\nROM patched successfully")
    print(f"  Output: {output_rom}")
    print(f"\nTest with:")
    print(f"  ./mgba-qt.sh {output_rom} -t save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0")


if __name__ == "__main__":
    main()
