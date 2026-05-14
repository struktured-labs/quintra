#!/usr/bin/env python3
"""
v2.27: Stage Detection + Jet Form Palettes + Per-Stage BG Colors

NEW in v2.27:
- **Stage detection** via 0xFFD0:
  - 0x00 = Level 1 (main dungeon) → BG palette 0 (Dungeon blue)
  - 0x01 = Bonus stage (jet/spaceship) → BG palette 7 (deep blue)
- **Jet form palettes**: Sara W Jet (magenta) and Sara D Jet (cyan) in bonus stage
- **Per-stage BG loading**: Different BG palettes load based on current stage

Boss detection via 0xFFBF still works:
  - 0xFFBF = 1 → Load Gargoyle colors into palette 6
  - 0xFFBF = 2 → Load Spider colors into palette 7
  - 0xFFBF = 0 → Normal tile-based coloring
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
    """Load BG, OBJ, boss, and jet form palettes from YAML file."""
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

    obj_keys = ['Effects', 'SaraDragon', 'SaraWitch', 'Crow',
                'Hornets', 'OrcGround', 'Humanoid', 'Catfish']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

    boss_data = data.get('boss_palettes', {})
    gargoyle = pal_to_bytes(boss_data.get('Gargoyle', {}).get('colors', ["0000", "601F", "400F", "0000"]))
    spider = pal_to_bytes(boss_data.get('Spider', {}).get('colors', ["0000", "001F", "00BF", "0000"]))

    # Load jet form palettes
    jet_data = data.get('obj_palettes', {})
    sara_witch_jet = pal_to_bytes(jet_data.get('SaraWitchJet', {}).get('colors', ["0000", "7C1F", "5817", "3010"]))
    sara_dragon_jet = pal_to_bytes(jet_data.get('SaraDragonJet', {}).get('colors', ["0000", "7FE0", "4EC0", "2D80"]))

    return bytes(bg_data), bytes(obj_data), gargoyle, spider, sara_witch_jet, sara_dragon_jet


def create_tile_based_colorizer() -> bytes:
    """
    Tile-based colorizer with boss/miniboss override.

    Input: HL = pointer to flags byte, D = Sara palette, E = boss flag (0=normal, 7=boss mode)

    Logic:
    - Slots 0-3: Sara (palette D)
    - Tile < 0x10: Projectile (palette 0)
    - If E != 0: Boss mode → palette 7 for all enemies
    - Otherwise tile-based:
      - 0x40-0x4F: Hornets (palette 4)
      - 0x50-0x5F: Orcs (palette 5)
      - 0x60-0x6F: Humanoids (palette 6)
      - 0x70-0x7F: Miniboss (palette 7)
      - Default: palette 4
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []  # (position, target_label)

    # LD B, 40
    code.extend([0x06, 0x28])

    # loop_start:
    labels['loop_start'] = len(code)

    # Check if Sara slot (0-3)
    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B (A = slot number 0-39)
    code.extend([0xFE, 0x04])        # CP 4
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])        # JR C, sara_palette (placeholder)

    # Read tile (at HL-1)
    code.append(0x2B)                # DEC HL
    code.append(0x7E)                # LD A, [HL] (tile)
    code.append(0x23)                # INC HL
    code.append(0x4F)                # LD C, A (save tile)

    # Check projectile (tile < 0x10)
    code.extend([0xFE, 0x10])        # CP 0x10
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])        # JR C, projectile_palette (placeholder)

    # Check boss/miniboss mode (E register)
    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])        # JR NZ, boss_palette (E != 0)

    # Normal mode: tile-based coloring
    code.append(0x79)                # LD A, C (restore tile)

    # Check tile ranges for monster types
    # Tile 0x40-0x4F: Hornets
    code.extend([0xFE, 0x50])        # CP 0x50
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])        # JR C, check_hornet (tile < 0x50)

    # Tile 0x50-0x5F: Orcs
    code.extend([0xFE, 0x60])        # CP 0x60
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])        # JR C, orc_palette (tile 0x50-0x5F)

    # Tile 0x60-0x6F: Humanoids
    code.extend([0xFE, 0x70])        # CP 0x70
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])        # JR C, humanoid_palette (tile 0x60-0x6F)

    # Tile 0x70-0x7F: Miniboss
    code.extend([0xFE, 0x80])        # CP 0x80
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])        # JR C, miniboss_palette (tile 0x70-0x7F)

    # Default: palette 4
    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # check_hornet: (tile < 0x50, check if >= 0x40)
    labels['check_hornet'] = len(code)
    code.append(0x79)                # LD A, C (restore tile)
    code.extend([0xFE, 0x40])        # CP 0x40
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])        # JR NC, hornet_palette (tile >= 0x40)
    # tile < 0x40, check if >= 0x30 (crow)
    code.extend([0xFE, 0x30])        # CP 0x30
    jumps_to_fix.append((len(code), 'crow_palette'))
    code.extend([0x30, 0x00])        # JR NC, crow_palette (tile >= 0x30)
    # tile < 0x30, default palette
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # sara_palette:
    labels['sara_palette'] = len(code)
    code.append(0x7A)                # LD A, D
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # projectile_palette:
    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # crow_palette:
    labels['crow_palette'] = len(code)
    code.extend([0x3E, 0x03])        # LD A, 3
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # hornet_palette:
    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # orc_palette:
    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])        # LD A, 5
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # humanoid_palette:
    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])        # LD A, 6
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # boss_palette:
    labels['boss_palette'] = len(code)
    code.append(0x7B)                # LD A, E (use boss palette from E register)
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # miniboss_palette:
    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7
    # fall through to apply_palette

    # apply_palette:
    labels['apply_palette'] = len(code)
    code.append(0x4F)                # LD C, A
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A

    # Next sprite
    code.extend([0x23, 0x23, 0x23, 0x23])  # INC HL x4
    code.append(0x05)                # DEC B
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])  # JR NZ, loop_start
    code.append(0xC9)                # RET

    # Fix all jump offsets
    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """Colorizes BOTH shadow buffers (0xC000 and 0xC100)."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Determine Sara palette (D)
    code.extend([0xF0, 0xBE])        # LDH A, [FFBE]
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x04])        # JR NZ, +4 (Dragon)
    code.extend([0x16, 0x02])        # LD D, 2 (Witch)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x16, 0x01])        # LD D, 1 (Dragon)

    # Check boss/miniboss flag at 0xFFBF
    # E = 6 if Gargoyle (flag=1), E = 7 if Spider (flag=2), E = 0 if normal
    code.extend([0xF0, 0xBF])        # LDH A, [0xFFBF]
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x28, 0x08])        # JR Z, +8 (Gargoyle)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x28, 0x06])        # JR Z, +6 (Spider)
    code.extend([0x1E, 0x00])        # LD E, 0 (normal mode)
    code.extend([0x18, 0x06])        # JR +6 (done)
    # Gargoyle:
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle palette)
    code.extend([0x18, 0x02])        # JR +2 (done)
    # Spider:
    code.extend([0x1E, 0x07])        # LD E, 7 (Spider palette)

    # Colorize shadow buffer 1 (0xC000)
    code.extend([0x21, 0x03, 0xC0])  # LD HL, 0xC003
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    # Colorize shadow buffer 2 (0xC100)
    code.extend([0x21, 0x03, 0xC1])  # LD HL, 0xC103
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                # RET
    return bytes(code)


def create_palette_loader(
    palette_data_addr: int,
    gargoyle_addr: int,
    spider_addr: int,
    sara_witch_jet_addr: int,
    sara_dragon_jet_addr: int
) -> bytes:
    """
    Load CGB palettes with stage detection and boss palette swapping.

    Stage detection (0xFFD0):
      stage=0x00: Level 1 → Load BG palette 0 (Dungeon)
      stage=0x01: Bonus stage → Load BG palette 7 (Spaceship) + Jet form OBJ palettes

    Boss detection (0xFFBF):
      boss_flag=1: Load Gargoyle into palette 6
      boss_flag=2: Load Spider into palette 7
    """
    code = bytearray()

    # === STAGE DETECTION: Check 0xFFD0 ===
    code.extend([0xF0, 0xD0])        # LDH A, [0xFFD0] (stage flag)
    code.append(0x47)                # LD B, A (save stage for later)

    # === LOAD ALL BG PALETTES (64 bytes = 8 palettes) ===
    # For now, load all 8 BG palettes from palette data
    # TODO: In future, could load different sets based on stage
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, palette 0)
    code.extend([0xE0, 0x68])        # LDH [FF68], A (BCPS)
    code.extend([0x0E, 0x40])        # LD C, 64 (all 8 BG palettes)
    # bg_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [FF69], A (BCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, bg_loop

    # === LOAD OBJ PALETTES 0-5, with stage-dependent palettes 1 and 2 ===
    obj_data_addr = palette_data_addr + 64

    # Palette 0: Effects (always same)
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, palette 0)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal0_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal0_loop

    # Palette 1: Sara Dragon (stage-dependent)
    code.extend([0x3E, 0x88])        # LD A, 0x88 (auto-increment, palette 1)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    sara_dragon_normal_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_normal_addr & 0xFF, (sara_dragon_normal_addr >> 8) & 0xFF])
    code.append(0x78)                # LD A, B (check stage)
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal1_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal1_loop

    # Palette 2: Sara Witch (stage-dependent)
    code.extend([0x3E, 0x90])        # LD A, 0x90 (auto-increment, palette 2)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    sara_witch_normal_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_normal_addr & 0xFF, (sara_witch_normal_addr >> 8) & 0xFF])
    code.append(0x78)                # LD A, B (check stage)
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal2_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal2_loop

    # Palettes 3-5: Crow, Hornets, Orc (always same)
    code.extend([0x3E, 0x98])        # LD A, 0x98 (auto-increment, palette 3)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])        # LD C, 24 (3 palettes)
    # pal35_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal35_loop

    # Palette 6: Humanoid OR Gargoyle (boss-dependent)
    code.extend([0x3E, 0xB0])        # LD A, 0xB0 (auto-increment, palette 6)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF] (boss flag)
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal6_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal6_loop

    # Palette 7: Catfish OR Spider (boss-dependent)
    code.extend([0x3E, 0xB8])        # LD A, 0xB8 (auto-increment, palette 7)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF] (boss flag)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal7_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal7_loop

    code.append(0xC9)                # RET
    return bytes(code)


def create_tile_palette_lookup() -> bytes:
    """256-byte lookup table: tile_id -> BG palette."""
    lookup = bytearray(256)
    for i in range(256):
        if i < 0x20:
            lookup[i] = 0   # Floor -> Palette 0 (blue)
        elif i < 0x80:
            lookup[i] = 2   # Walls -> Palette 2 (purple)
        elif i < 0xE0:
            lookup[i] = 1   # Items -> Palette 1 (gold)
        elif i == 0xFF:
            lookup[i] = 0   # Void -> Palette 0
        else:
            lookup[i] = 2   # Borders -> Palette 2
    return bytes(lookup)


def create_bg_colorizer_oneshot(lookup_table_addr: int) -> bytes:
    """
    One-shot BG colorizer - processes 1 row per VBlank.
    Uses HRAM 0xFFE0 for row counter. Completes in 18 VBlanks.
    """
    code = bytearray()

    # Check row counter
    code.extend([0xF0, 0xE0])              # LDH A, [0xFFE0]
    code.extend([0xFE, 0x12])              # CP 18
    code.extend([0xD0])                    # RET NC (if >= 18, done)

    # Row calculation: HL = 0x9800 + row * 32
    code.append(0xC5)                      # PUSH BC
    code.append(0xD5)                      # PUSH DE
    code.append(0x6F)                      # LD L, A
    code.extend([0x26, 0x00])              # LD H, 0
    code.append(0x29)                      # ADD HL, HL (*2)
    code.append(0x29)                      # ADD HL, HL (*4)
    code.append(0x29)                      # ADD HL, HL (*8)
    code.append(0x29)                      # ADD HL, HL (*16)
    code.append(0x29)                      # ADD HL, HL (*32)
    code.extend([0x01, 0x00, 0x98])        # LD BC, 0x9800
    code.append(0x09)                      # ADD HL, BC

    # Process 32 tiles
    code.extend([0x06, 0x20])              # LD B, 32

    tile_loop_start = len(code)

    # Ensure VBK is 0 (read tile IDs)
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A
    code.append(0x56)                      # LD D, [HL]

    # Look up palette
    code.append(0xE5)                      # PUSH HL
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])  # LD H, table_hi
    code.append(0x7A)                      # LD A, D
    code.append(0x6F)                      # LD L, A
    code.append(0x5E)                      # LD E, [HL]
    code.append(0xE1)                      # POP HL

    # Write palette to bank 1
    code.extend([0x3E, 0x01])              # LD A, 1
    code.extend([0xE0, 0x4F])              # LDH [VBK], A
    code.append(0x73)                      # LD [HL], E

    code.append(0x23)                      # INC HL
    code.append(0x05)                      # DEC B
    tile_offset = tile_loop_start - len(code) - 2
    code.extend([0x20, tile_offset & 0xFF])

    # Restore registers
    code.append(0xD1)                      # POP DE
    code.append(0xC1)                      # POP BC

    # Update HRAM counter
    code.extend([0xF0, 0xE0])              # LDH A, [0xFFE0]
    code.extend([0xC6, 0x01])              # ADD A, 1
    code.extend([0xE0, 0xE0])              # LDH [0xFFE0], A

    # Reset VBK
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    code.append(0xC9)                      # RET
    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function: load palettes, colorize shadows, colorize BG, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # CALL DMA
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook at 0x0824 with input handler."""
    simplified_input = bytearray([
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
    ])
    hook_code = bytearray([
        0x3E, 0x0D, 0xEA, 0x00, 0x20,
        0xCD, combined_func_addr & 0xFF, combined_func_addr >> 8,
        0x3E, 0x01, 0xEA, 0x00, 0x20,
        0xC9,
    ])
    return bytes(simplified_input + hook_code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.27 ===")
    print("Stage detection + Jet form palettes + Per-stage BG colors")

    # Load ROM
    with open(input_rom, "rb") as f:
        rom_data = bytearray(f.read())

    # Load palettes
    bg_data, obj_data, gargoyle, spider, sara_witch_jet, sara_dragon_jet = load_palettes_from_yaml(palette_yaml)

    # Bank 13 layout
    BANK_13_START = 0x4C000
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    sara_witch_jet_addr = 0x6890
    sara_dragon_jet_addr = 0x6898
    palette_loader_addr = 0x6900  # 143 bytes → ends at 0x698F
    shadow_main_addr = 0x6990     # 52 bytes → ends at 0x69C4
    colorizer_addr = 0x69D0       # 97 bytes → ends at 0x6A31
    combined_func_addr = 0x6A80   # 13 bytes → ends at 0x6A8D
    lookup_table_addr = 0x6B00    # 256 bytes
    bg_colorizer_addr = 0x6C00    # 53 bytes

    # Generate code
    palette_loader = create_palette_loader(
        palette_data_addr, gargoyle_addr, spider_addr,
        sara_witch_jet_addr, sara_dragon_jet_addr
    )
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    colorizer = create_tile_based_colorizer()
    lookup_table = create_tile_palette_lookup()
    bg_colorizer = create_bg_colorizer_oneshot(lookup_table_addr)
    combined_func = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_func_addr)

    # Apply display patches first
    apply_all_display_patches(rom_data)

    # Write to Bank 13
    def write_bank13(addr: int, data: bytes):
        offset = BANK_13_START + (addr - 0x4000)
        rom_data[offset:offset + len(data)] = data

    write_bank13(palette_data_addr, bg_data + obj_data)
    write_bank13(gargoyle_addr, gargoyle)
    write_bank13(spider_addr, spider)
    write_bank13(sara_witch_jet_addr, sara_witch_jet)
    write_bank13(sara_dragon_jet_addr, sara_dragon_jet)
    write_bank13(palette_loader_addr, palette_loader)
    write_bank13(shadow_main_addr, shadow_main)
    write_bank13(colorizer_addr, colorizer)
    write_bank13(lookup_table_addr, lookup_table)
    write_bank13(bg_colorizer_addr, bg_colorizer)
    write_bank13(combined_func_addr, combined_func)

    # Write VBlank hook at 0x0824 (bank 0)
    rom_data[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Write output
    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom_data)

    print(f"✓ ROM patched successfully")
    print(f"  Stage detection: 0xFFD0")
    print(f"  - 0x00 = Level 1 (BG palette 0)")
    print(f"  - 0x01 = Bonus stage (BG palette 7 + jet palettes)")
    print(f"  Output: {output_rom}")
    print(f"  Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"  Shadow colorizer: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"  Tile colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"  BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")


if __name__ == "__main__":
    main()
