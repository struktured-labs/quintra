#!/usr/bin/env python3
"""
v2.55: Scroll-edge priority BG colorizer

v2.54 achieved 100% static accuracy but dropped to ~94% during scrolling because
the linear sweep takes ~5 frames to revisit scroll-edge tiles that the game
continuously overwrites.

v2.55 fix: prioritize BOTH viewport edge columns every frame BEFORE the sweep.
- Phase 1: Right-edge column (32 tiles) - handles newly scrolled-in tiles
- Phase 2: Left-edge column (32 tiles) - handles outgoing stale palettes
- Phase 3: Linear sweep (128 tiles) - handles everything else
Total: 192 tiles/frame (~35% CPU budget)

The edge columns are computed from SCX (horizontal scroll register):
- Right edge: (SCX + 160) / 8 & 0x1F (column just past right viewport edge)
- Left edge: (SCX / 8 - 1) & 0x1F (column just past left viewport edge)

This ensures scroll-edge tiles are colorized every frame instead of every ~5 frames.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> dict:
    """Load all palette data from YAML file."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors: list[str]) -> bytes:
        result = bytearray()
        for c in colors:
            val = int(c, 16) & 0x7FFF
            result.extend([val & 0xFF, (val >> 8) & 0xFF])
        return bytes(result)

    bg_keys = ['Dungeon', 'BG1', 'BG2', 'BG3', 'BG4', 'BG5', 'BG6', 'BG7']
    bg_data = bytearray()
    for key in bg_keys:
        if key in data.get('bg_palettes', {}):
            bg_data.extend(pal_to_bytes(data['bg_palettes'][key]['colors']))
        else:
            bg_data.extend(pal_to_bytes(["7FFF", "5294", "2108", "0000"]))

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

    jet_data = data.get('obj_palettes', {})
    sara_witch_jet = pal_to_bytes(jet_data.get('SaraWitchJet', {}).get('colors', ["0000", "7C1F", "5817", "3010"]))
    sara_dragon_jet = pal_to_bytes(jet_data.get('SaraDragonJet', {}).get('colors', ["0000", "7FE0", "4EC0", "2D80"]))

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
    """Tile-based OBJ colorizer. Unchanged from v2.33."""
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
    emit([0x3E, 0x28, 0x90, 0xFE, 0x04])
    emit_jr(0x38, 'sara_palette')
    emit([0x2B, 0x7E, 0x23, 0x4F])
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
    """Shadow colorizer main - processes BOTH shadow OAM buffers."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    code.extend([0xF0, 0xBE, 0xB7, 0x20, 0x04])
    code.extend([0x16, 0x02, 0x18, 0x02])
    code.extend([0x16, 0x01])

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

    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])

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

    code.extend([0x3E, 0x88, 0xE0, 0x6A])
    sara_dragon_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_addr & 0xFF, (sara_dragon_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0x90, 0xE0, 0x6A])
    sara_witch_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_addr & 0xFF, (sara_witch_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0x98, 0xE0, 0x6A])
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0xB0, 0xE0, 0x6A])
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0xB8, 0xE0, 0x6A])
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

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
    code.extend([0x87, 0x87, 0x87])
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
    """Tile->palette subroutine for OBJ colorizer (CALL-based).

    Input: A = tile ID
    Output: A = palette number (0, 1, 6) or 0xFF = skip marker
    """
    code = bytearray()
    code.extend([0xFE, 0xFF])   # CP 0xFF
    code.extend([0xC8])         # RET Z
    cp1 = len(code); code.extend([0xFE, 0x05, 0x38, 0x00])
    cp2 = len(code); code.extend([0xFE, 0x07, 0x38, 0x00])
    cp3 = len(code); code.extend([0xFE, 0x13, 0x38, 0x00])
    cp4 = len(code); code.extend([0xFE, 0x60, 0x38, 0x00])
    cp5 = len(code); code.extend([0xFE, 0x88, 0x38, 0x00])
    cp6 = len(code); code.extend([0xFE, 0xE0, 0x38, 0x00])
    cp7 = len(code); code.extend([0xFE, 0xFE, 0x38, 0x00])
    pal0 = len(code); code.extend([0xAF, 0xC9])
    pal1 = len(code); code.extend([0x3E, 0x01, 0xC9])
    pal6 = len(code); code.extend([0x3E, 0x06, 0xC9])
    code[cp1 + 3] = (pal0 - (cp1 + 4)) & 0xFF
    code[cp2 + 3] = (pal6 - (cp2 + 4)) & 0xFF
    code[cp3 + 3] = (pal0 - (cp3 + 4)) & 0xFF
    code[cp4 + 3] = (pal6 - (cp4 + 4)) & 0xFF
    code[cp5 + 3] = (pal0 - (cp5 + 4)) & 0xFF
    code[cp6 + 3] = (pal1 - (cp6 + 4)) & 0xFF
    code[cp7 + 3] = (pal6 - (cp7 + 4)) & 0xFF
    return bytes(code)


def create_bg_tile_table() -> bytes:
    """256-byte ROM lookup table: tile_id -> BG palette number.

    Returns 0xFF for tile 0xFF (garbage VRAM read filter).
    Detailed per-tile classification for accurate wall/floor distinction.
    """
    table = bytearray(256)
    for tile in range(256):
        if tile == 0xFF:
            table[tile] = 0xFF  # skip marker
        elif tile < 0x05:
            table[tile] = 0     # floor checkerboard
        elif tile < 0x07:
            table[tile] = 6     # platform corners
        elif tile < 0x13:
            table[tile] = 0     # floor edges
        elif tile < 0x60:
            table[tile] = 6     # structural + platforms + walls
        elif tile < 0x88:
            table[tile] = 0     # arch/doorway/UI
        elif tile < 0xE0:
            table[tile] = 1     # items (gold)
        elif tile < 0xFE:
            table[tile] = 6     # decorative/structural
        else:
            table[tile] = 0     # void (0xFE)
    return bytes(table)


def create_bg_colorizer(bg_table_addr: int) -> bytes:
    """BG colorizer with scroll-edge priority + linear sweep.

    Phase 1: Right-edge column (32 tiles, stride-32) - newly scrolled-in tiles
    Phase 2: Left-edge column (32 tiles, stride-32) - outgoing stale palettes
    Phase 3: Linear sweep (128 tiles, stride-1) - everything else
    Total: 192 tiles/frame

    Uses ROM lookup table + 0xFF anti-flicker filter + safe HRAM.
    """
    EDGE_TILES = 32    # per column
    SWEEP_TILES = 128
    bg_table_hi = (bg_table_addr >> 8) & 0xFF

    code = bytearray()

    # === CHECK GAME MODE ===
    code.extend([0xF0, 0xC1])        # LDH A, [FFC1]
    code.extend([0xB7])              # OR A
    code.extend([0xC8])              # RET Z (skip on menus)

    code.extend([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL

    # === DETERMINE ACTIVE TILEMAP ===
    code.extend([0xF0, 0x40])        # LDH A, [FF40]    ; LCDC
    code.extend([0xE6, 0x08])        # AND 0x08          ; bit 3
    code.extend([0xCB, 0x3F])        # SRL A             ; 0->0, 8->4
    code.extend([0xC6, 0x98])        # ADD A, 0x98       ; 0x98 or 0x9C
    code.extend([0xE0, 0xA9])        # LDH [FFA9], A     ; save base_hi

    # Set H = table high byte (persists through ALL phases)
    code.extend([0x26, bg_table_hi])  # LD H, table_hi

    # Ensure VRAM bank 0
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A

    # =======================================================
    # PHASE 1: RIGHT-EDGE COLUMN (just past right viewport)
    # Column = (SCX + 160) / 8 & 0x1F
    # =======================================================
    code.extend([0xF0, 0x43])        # LDH A, [FF43]     ; SCX
    code.extend([0xC6, 0xA0])        # ADD A, 160         ; wraps at 256 = tilemap wrap
    code.extend([0x0F, 0x0F, 0x0F])  # RRCA x3            ; /8
    code.extend([0xE6, 0x1F])        # AND 0x1F           ; column 0-31
    code.extend([0x5F])              # LD E, A
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x57])              # LD D, A            ; DE = tilemap base + column
    code.extend([0x06, EDGE_TILES])  # LD B, 32

    # --- Edge column loop (stride-32) ---
    edge_loop_start = len(code)

    # Read tile + ROM table lookup
    code.extend([0x1A])              # LD A, [DE]         ; read tile
    code.extend([0x6F])              # LD L, A            ; table index
    code.extend([0x7E])              # LD A, [HL]         ; palette from table
    # 0xFF filter
    code.extend([0xFE, 0xFF])        # CP 0xFF
    edge_skip_pos = len(code)
    code.extend([0x28, 0x00])        # JR Z, skip_write
    # Write palette to VRAM bank 1
    code.extend([0x4F])              # LD C, A
    code.extend([0x3E, 0x01])        # LD A, 1
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A      ; bank 1
    code.extend([0x79])              # LD A, C
    code.extend([0x12])              # LD [DE], A          ; write attr
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A      ; bank 0
    edge_skip_target = len(code)
    code[edge_skip_pos + 1] = edge_skip_target - (edge_skip_pos + 2)

    # Advance DE by 32 (next row, same column)
    code.extend([0x7B])              # LD A, E
    code.extend([0xC6, 0x20])        # ADD A, 32
    code.extend([0x5F])              # LD E, A
    edge_nc_pos = len(code)
    code.extend([0x30, 0x00])        # JR NC, no_carry
    code.extend([0x14])              # INC D
    edge_nc_target = len(code)
    code[edge_nc_pos + 1] = edge_nc_target - (edge_nc_pos + 2)

    # Wrap check (D must stay within base..base+3)
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0xC6, 0x04])        # ADD A, 4
    code.extend([0xBA])              # CP D
    edge_nw_pos = len(code)
    code.extend([0x20, 0x00])        # JR NZ, no_wrap
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x57])              # LD D, A
    edge_nw_target = len(code)
    code[edge_nw_pos + 1] = edge_nw_target - (edge_nw_pos + 2)

    # Loop
    code.extend([0x05])              # DEC B
    edge_loop_end = len(code)
    edge_jr = edge_loop_start - (edge_loop_end + 2)
    code.extend([0x20, edge_jr & 0xFF])

    # =======================================================
    # PHASE 2: LEFT-EDGE COLUMN (just past left viewport)
    # Column = (SCX / 8 - 1) & 0x1F
    # =======================================================
    code.extend([0xF0, 0x43])        # LDH A, [FF43]     ; SCX
    code.extend([0x0F, 0x0F, 0x0F])  # RRCA x3            ; /8
    code.extend([0x3D])              # DEC A               ; -1
    code.extend([0xE6, 0x1F])        # AND 0x1F           ; column 0-31
    code.extend([0x5F])              # LD E, A
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x57])              # LD D, A
    code.extend([0x06, EDGE_TILES])  # LD B, 32

    # --- Left edge column loop (same structure, reuse by jumping back) ---
    # Jump back to the shared edge loop
    left_jr_pos = len(code)
    left_jr_offset = edge_loop_start - (left_jr_pos + 2)
    code.extend([0x18, left_jr_offset & 0xFF])  # JR edge_loop_start

    # When B reaches 0 after phase 2, execution falls through from edge loop end
    # to here. But wait - the JR NZ at edge_loop_end won't fall through to here
    # because phase 2's JR jumped INTO the middle of phase 1's loop.
    # After phase 2's loop (B=0), the JR NZ at edge_loop_end falls through
    # to the code right after edge_loop_end, which is... the phase 2 setup!
    # That would re-execute phase 2 in an infinite loop.
    #
    # FIX: Don't reuse the loop. Use two inline loops instead.

    # SCRATCH THE REUSE APPROACH - revert to two inline loops
    # Remove the JR we just added
    del code[left_jr_pos:]

    # --- Left edge column loop (inline copy of edge loop) ---
    edge2_loop_start = len(code)

    code.extend([0x1A])              # LD A, [DE]
    code.extend([0x6F])              # LD L, A
    code.extend([0x7E])              # LD A, [HL]
    code.extend([0xFE, 0xFF])        # CP 0xFF
    edge2_skip_pos = len(code)
    code.extend([0x28, 0x00])        # JR Z, skip
    code.extend([0x4F])              # LD C, A
    code.extend([0x3E, 0x01])        # LD A, 1
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A
    code.extend([0x79])              # LD A, C
    code.extend([0x12])              # LD [DE], A
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A
    edge2_skip_target = len(code)
    code[edge2_skip_pos + 1] = edge2_skip_target - (edge2_skip_pos + 2)

    code.extend([0x7B])              # LD A, E
    code.extend([0xC6, 0x20])        # ADD A, 32
    code.extend([0x5F])              # LD E, A
    edge2_nc_pos = len(code)
    code.extend([0x30, 0x00])        # JR NC, no_carry
    code.extend([0x14])              # INC D
    edge2_nc_target = len(code)
    code[edge2_nc_pos + 1] = edge2_nc_target - (edge2_nc_pos + 2)

    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0xC6, 0x04])        # ADD A, 4
    code.extend([0xBA])              # CP D
    edge2_nw_pos = len(code)
    code.extend([0x20, 0x00])        # JR NZ, no_wrap
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x57])              # LD D, A
    edge2_nw_target = len(code)
    code[edge2_nw_pos + 1] = edge2_nw_target - (edge2_nw_pos + 2)

    code.extend([0x05])              # DEC B
    edge2_loop_end = len(code)
    edge2_jr = edge2_loop_start - (edge2_loop_end + 2)
    code.extend([0x20, edge2_jr & 0xFF])

    # =======================================================
    # PHASE 3: LINEAR SWEEP (standard sweep from saved position)
    # =======================================================
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x4F])              # LD C, A
    code.extend([0xF0, 0xA5])        # LDH A, [FFA5]     ; counter high
    code.extend([0xE6, 0x03])        # AND 0x03
    code.extend([0x81])              # ADD A, C
    code.extend([0x57])              # LD D, A
    code.extend([0xF0, 0x91])        # LDH A, [FF91]     ; counter low
    code.extend([0x5F])              # LD E, A
    code.extend([0x06, SWEEP_TILES]) # LD B, 128

    # --- Sweep loop (stride-1) ---
    sweep_start = len(code)

    code.extend([0x1A])              # LD A, [DE]
    code.extend([0x6F])              # LD L, A
    code.extend([0x7E])              # LD A, [HL]
    code.extend([0xFE, 0xFF])        # CP 0xFF
    sweep_skip_pos = len(code)
    code.extend([0x28, 0x00])        # JR Z, skip
    code.extend([0x4F])              # LD C, A
    code.extend([0x3E, 0x01])        # LD A, 1
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A
    code.extend([0x79])              # LD A, C
    code.extend([0x12])              # LD [DE], A
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A
    sweep_skip_target = len(code)
    code[sweep_skip_pos + 1] = sweep_skip_target - (sweep_skip_pos + 2)

    # Advance DE by 1
    code.extend([0x13])              # INC DE

    # Wrap check
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0xC6, 0x04])        # ADD A, 4
    code.extend([0xBA])              # CP D
    sweep_nw_pos = len(code)
    code.extend([0x20, 0x00])        # JR NZ, no_wrap
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]
    code.extend([0x57])              # LD D, A
    sweep_nw_target = len(code)
    code[sweep_nw_pos + 1] = sweep_nw_target - (sweep_nw_pos + 2)

    code.extend([0x05])              # DEC B
    sweep_end = len(code)
    sweep_jr = sweep_start - (sweep_end + 2)
    if sweep_jr < -128:
        raise ValueError(f"Sweep loop JR offset {sweep_jr} out of range!")
    code.extend([0x20, sweep_jr & 0xFF])

    # === SAVE SWEEP POSITION ===
    code.extend([0x7A])              # LD A, D
    code.extend([0xE6, 0x03])        # AND 0x03
    code.extend([0xE0, 0xA5])        # LDH [FFA5], A
    code.extend([0x7B])              # LD A, E
    code.extend([0xE0, 0x91])        # LDH [FF91], A

    # === CLEANUP ===
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A     ; VRAM bank 0

    code.extend([0xE1, 0xD1, 0xC1])  # POP HL, DE, BC
    code.extend([0xC9])              # RET

    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined: BG -> Palette -> OBJ -> DMA."""
    code = bytearray()
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF, 0xC9])
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook - v2.36 STABLE style.

    1 d-pad read + 8 button reads (loop) + explicit bank restore.
    This is the EXACT hook from v2.36 which had zero ship mode issues.
    """
    lo = combined_func_addr & 0xFF
    hi = (combined_func_addr >> 8) & 0xFF

    joypad_input = bytearray([
        # D-pad (1 read - d-pad matrix settles fast)
        0x3E, 0x20,        # LD A, 0x20        ; select d-pad
        0xE0, 0x00,        # LDH [FF00], A
        0xF0, 0x00,        # LDH A, [FF00]     ; read d-pad
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xCB, 0x37,        # SWAP A            ; d-pad to upper nibble
        0x47,              # LD B, A            ; save in B
        # Buttons (8 reads via loop)
        0x3E, 0x10,        # LD A, 0x10        ; select buttons
        0xE0, 0x00,        # LDH [FF00], A
        0x0E, 0x08,        # LD C, 8           ; read 8 times
        0xF0, 0x00,        # .loop: LDH A,[FF00]
        0x0D,              # DEC C
        0x20, 0xFB,        # JR NZ, .loop
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xB0,              # OR B              ; combine
        0xE0, 0x93,        # LDH [FF93], A
        # Deselect joypad
        0x3E, 0x30,        # LD A, 0x30
        0xE0, 0x00,        # LDH [FF00], A
    ])  # 33 bytes

    hook_code = bytearray([
        0x3E, 0x0D,              # LD A, 0x0D       ; bank 13
        0xEA, 0x00, 0x20,        # LD [0x2000], A
        0xCD, lo, hi,            # CALL combined
        0x3E, 0x01,              # LD A, 0x01       ; bank 1 (explicit)
        0xEA, 0x00, 0x20,        # LD [0x2000], A
        0xC9,                    # RET
    ])  # 14 bytes

    total = joypad_input + hook_code
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be exactly 47!"
    return bytes(total)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.55 ===")
    print("Scroll-edge priority BG (edges + sweep = 192 tiles) + v2.36 hook (no ship mode)")
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
    tile_to_pal_addr = 0x6B00  # subroutine for OBJ colorizer
    bg_colorizer_addr = 0x6C00
    combined_addr = 0x6D00
    bg_table_addr = 0x6E00     # 256-byte ROM lookup table for BG

    # Generate code
    palette_loader = create_palette_loader(
        palette_data_addr, boss_palette_table_addr, boss_slot_table_addr,
        sara_witch_jet_addr, sara_dragon_jet_addr,
        spiral_proj_addr, shield_proj_addr, turbo_proj_addr,
    )
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_table_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_to_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table()
    bg_colorizer = create_bg_colorizer(bg_table_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    # Print sizes
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"OBJ colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Tile->pal sub: {len(tile_to_pal)} bytes at 0x{tile_to_pal_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"BG tile table: {len(bg_table)} bytes at 0x{bg_table_addr:04X}")
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
        ('bg_table', bg_table_addr, len(bg_table)),
    ]
    for i, (name_a, start_a, size_a) in enumerate(regions):
        for name_b, start_b, size_b in regions[i + 1:]:
            end_a = start_a + size_a
            end_b = start_b + size_b
            if start_a < end_b and start_b < end_a:
                raise ValueError(f"OVERLAP: {name_a} (0x{start_a:04X}-0x{end_a:04X}) "
                                 f"and {name_b} (0x{start_b:04X}-0x{end_b:04X})")

    bank13_offset = 13 * 0x4000
    max_addr = 0x4000 + 0x4000  # Bank 13 ends at 0x7FFF

    def write_bank13(addr, data):
        if addr + len(data) > max_addr:
            raise ValueError(f"Data at 0x{addr:04X} extends past bank 13 boundary!")
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
    write_bank13(bg_table_addr, bg_table)
    write_bank13(combined_addr, combined)

    # Patch ROM hooks
    rom[0x06D5:0x06D5 + 3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    rom[0x143] = 0x80
    print(f"\nSet CGB flag at 0x143")

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom)

    print(f"\nROM patched successfully -> {output_rom}")
    print(f"Total bank 13 usage: 0x6800-0x{bg_table_addr + len(bg_table) - 1:04X} "
          f"({bg_table_addr + len(bg_table) - 0x6800} bytes)")


if __name__ == "__main__":
    main()
