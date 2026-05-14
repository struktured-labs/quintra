#!/usr/bin/env python3
"""
v2.03: Phase 1 - Static BG Colorization with Tile→Palette Lookup

Strategy:
1. Keep working OBJ colorization from v1.09
2. Build 256-byte tile→palette lookup table in ROM at 0x6B00
3. Build attribute buffer (0xD000) from tile buffer (0xC1A0) using lookup
4. GDMA copy attributes to VBK 1 during VBlank

This is the "static proof of concept" - colors tiles based on their ID.
For scrolling support, we'll need to hook the tile update routine in Phase 2.

Memory Layout:
  0xC1A0-0xC4A0: Tile buffer (768 bytes) - game managed
  0xD000-0xD300: Attribute buffer (768 bytes) - we create
  0x6B00-0x6BFF: Tile→Palette lookup table (256 bytes) - ROM

Tile Category → Palette Mapping:
  0x00:         Empty → Palette 0 (transparent)
  0x01-0x06:    Floor → Palette 0 (blue checkerboard)
  0x13-0x3F:    Structure/Platforms → Palette 0
  0x40-0x5B:    Walls → Palette 2 (gray stone)
  0x60-0x7F:    Decorations → Palette 2
  0x88-0xDF:    Items → Palette 1 (gold/yellow)
  0xE0-0xFF:    Borders → Palette 0
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
    """Load BG, OBJ, and boss palettes from YAML file."""
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

    return bytes(bg_data), bytes(obj_data), gargoyle, spider


def create_tile_palette_lookup() -> bytes:
    """
    Create 256-byte lookup table: tile_id → BG palette number.

    Based on bg_tile_categories.yaml analysis:
      Palette 0: Floor, platforms, default (blue dungeon)
      Palette 1: Items (gold/yellow) - 0x88-0xDF
      Palette 2: Walls, structures (gray stone) - 0x40-0x7F
      Palette 3: Hazards (red) - specific tiles only
    """
    lookup = bytearray(256)

    for tile_id in range(256):
        palette = 0  # Default: dungeon blue

        # Items (0x88-0xDF) → Palette 1 (gold)
        if 0x88 <= tile_id <= 0xDF:
            palette = 1

        # Walls and structures (0x40-0x7F) → Palette 2 (stone gray)
        elif 0x40 <= tile_id <= 0x7F:
            palette = 2

        # Hazard tiles (specific) → Palette 3 (red/warning)
        # 0x2A-0x2E = spike cylinders, 0x3A-0x3D = more spikes
        elif tile_id in [0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x3A, 0x3B, 0x3C, 0x3D]:
            palette = 3

        # Everything else: Palette 0 (default dungeon)
        # This includes: 0x00 (empty), 0x01-0x06 (floor), 0x07-0x3F (platforms),
        # 0xE0-0xFF (borders)

        lookup[tile_id] = palette

    return bytes(lookup)


def create_tile_based_colorizer() -> bytes:
    """
    Tile-based OBJ colorizer with boss/miniboss override (from v1.09).
    Unchanged - this is the working sprite colorization.
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    code.extend([0x06, 0x28])  # LD B, 40
    labels['loop_start'] = len(code)

    # Check if Sara slot (0-3)
    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B
    code.extend([0xFE, 0x04])        # CP 4
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])        # JR C, sara_palette

    # Read tile (at HL-1)
    code.append(0x2B)                # DEC HL
    code.append(0x7E)                # LD A, [HL] (tile)
    code.append(0x23)                # INC HL
    code.append(0x4F)                # LD C, A (save tile)

    # Check projectile (tile < 0x10)
    code.extend([0xFE, 0x10])        # CP 0x10
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])        # JR C, projectile_palette

    # Check boss/miniboss mode (E register)
    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])        # JR NZ, boss_palette

    # Normal mode: tile-based coloring
    code.append(0x79)                # LD A, C (restore tile)

    # Tile ranges for monster types
    code.extend([0xFE, 0x50])        # CP 0x50
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])        # JR C, check_hornet

    code.extend([0xFE, 0x60])        # CP 0x60
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])        # JR C, orc_palette

    code.extend([0xFE, 0x70])        # CP 0x70
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])        # JR C, humanoid_palette

    code.extend([0xFE, 0x80])        # CP 0x80
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])        # JR C, miniboss_palette

    # Default: palette 4
    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # check_hornet: (tile < 0x50, check if >= 0x40)
    labels['check_hornet'] = len(code)
    code.append(0x79)                # LD A, C (restore tile)
    code.extend([0xFE, 0x40])        # CP 0x40
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])        # JR NC, hornet_palette
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['sara_palette'] = len(code)
    code.append(0x7A)                # LD A, D
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['boss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])        # LD A, 5
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])        # LD A, 6
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7

    labels['apply_palette'] = len(code)
    code.append(0x4F)                # LD C, A
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A

    code.extend([0x23, 0x23, 0x23, 0x23])  # INC HL x4
    code.append(0x05)                # DEC B
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])  # JR NZ, loop_start
    code.append(0xC9)                # RET

    # Fix jump offsets
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

    # Check boss flag
    code.extend([0xF0, 0xBF])        # LDH A, [0xFFBF]
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x28, 0x08])        # JR Z, +8 (Gargoyle)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x28, 0x06])        # JR Z, +6 (Spider)
    code.extend([0x1E, 0x00])        # LD E, 0 (normal mode)
    code.extend([0x18, 0x06])        # JR +6 (done)
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle palette)
    code.extend([0x18, 0x02])        # JR +2 (done)
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


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes with dynamic boss palette swapping."""
    code = bytearray()

    # Load BG palettes (64 bytes)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment)
    code.extend([0xE0, 0x68])        # LDH [FF68], A (BCPS)
    code.extend([0x0E, 0x40])        # LD C, 64
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [FF69], A (BCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, -6

    # Load OBJ palettes 0-5 (48 bytes)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    code.extend([0x0E, 0x30])        # LD C, 48
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, -6

    # Palette 6: Gargoyle check
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF]
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, -6

    # Palette 7: Spider check
    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF]
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, -6

    code.append(0xC9)                # RET
    return bytes(code)


def create_build_bg_attributes(lookup_table_addr: int) -> bytes:
    """
    Build BG attribute buffer from tile buffer using lookup table.

    Reads tile IDs from 0xC1A0, looks up palette in table at lookup_table_addr,
    writes palette numbers to 0xD000.

    Processes 768 bytes (24 rows × 32 columns).
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # DE = tile buffer (source)
    # HL = attribute buffer (dest)
    # BC = lookup table base (kept in B=high byte, we'll use A for indexing)
    code.extend([0x11, 0xA0, 0xC1])  # LD DE, 0xC1A0 (tile buffer)
    code.extend([0x21, 0x00, 0xD0])  # LD HL, 0xD000 (attribute buffer)

    # We need to process 768 bytes (24 rows × 32 cols)
    # Outer loop: 3 iterations of 256 bytes each
    code.extend([0x06, 0x03])        # LD B, 3 (outer loop counter)

    # outer_loop:
    outer_loop_start = len(code)
    code.extend([0x0E, 0x00])        # LD C, 0 (256 iterations inner loop)

    # inner_loop:
    inner_loop_start = len(code)

    # Read tile ID from [DE]
    code.append(0x1A)                # LD A, [DE]

    # Save A to stack temporarily
    code.append(0xF5)                # PUSH AF

    # Look up palette: table_addr + tile_id
    # Use HL' (we'll use stack) - actually let's use different approach
    # Save HL (dest pointer) to stack
    code.append(0xE5)                # PUSH HL

    # HL = lookup_table_addr + A (tile_id)
    code.extend([0x21, lookup_table_addr & 0xFF, (lookup_table_addr >> 8) & 0xFF])  # LD HL, lookup_table
    code.extend([0x5F])              # LD E, A (save tile_id in E temporarily)
    code.extend([0x16, 0x00])        # LD D, 0
    code.append(0x19)                # ADD HL, DE (HL = table + tile_id)
    code.append(0x7E)                # LD A, [HL] (A = palette number)

    # Restore dest pointer
    code.append(0xE1)                # POP HL

    # Also restore DE (but we clobbered it) - need to recalculate
    # Actually, let's rewrite this more carefully to preserve DE

    # Clear and restart the function with a better approach
    code = bytearray()

    # More efficient approach: use BC for lookup table, DE for source, HL for dest
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # BC = lookup table high byte (for quick lookup)
    code.extend([0x01, lookup_table_addr & 0xFF, (lookup_table_addr >> 8) & 0xFF])  # LD BC, lookup_table
    code.extend([0x11, 0xA0, 0xC1])  # LD DE, 0xC1A0 (tile buffer)
    code.extend([0x21, 0x00, 0xD0])  # LD HL, 0xD000 (attribute buffer)

    # We'll use a simple unrolled approach - process 768 bytes
    # Using HRAM counter for outer loop
    code.extend([0x3E, 0x03])        # LD A, 3
    code.extend([0xE0, 0xC8])        # LDH [FFC8], A (outer loop counter)

    # outer_loop:
    outer_loop = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0 (will count 256)
    code.extend([0xE0, 0xC9])        # LDH [FFC9], A (inner loop counter)

    # inner_loop:
    inner_loop = len(code)

    # Read tile ID from [DE]
    code.append(0x1A)                # LD A, [DE]
    code.append(0x13)                # INC DE

    # Lookup: BC + A = table entry address
    # Push DE, use DE for addition
    code.append(0xD5)                # PUSH DE
    code.extend([0x5F])              # LD E, A
    code.extend([0x50])              # LD D, B (high byte of lookup table)
    # Wait, that's not quite right. Let me think...

    # BC = base address of lookup table
    # We want: palette = [BC + tile_id]
    # A = tile_id
    # We can use: LD L, C; LD H, B; ADD L, A; ADC H, 0; LD A, [HL]

    code = bytearray()

    # Simplest approach: preload lookup table high byte, use low byte for indexing
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Use HRAM for counters
    # FFC8 = outer loop counter (3)
    # FFC9 = inner loop counter (256)

    code.extend([0x11, 0xA0, 0xC1])  # LD DE, 0xC1A0 (tile source)
    code.extend([0x21, 0x00, 0xD0])  # LD HL, 0xD000 (attr dest)

    # Outer loop: 3 iterations
    code.extend([0x3E, 0x03])        # LD A, 3
    code.extend([0xE0, 0xC8])        # LDH [FFC8], A

    # outer_loop:
    outer_start = len(code)

    # Inner loop: 256 iterations
    code.extend([0x3E, 0x00])        # LD A, 0 (256 iterations)
    code.extend([0xE0, 0xC9])        # LDH [FFC9], A

    # inner_loop:
    inner_start = len(code)

    # Read tile from source
    code.append(0x1A)                # LD A, [DE]
    code.append(0x13)                # INC DE

    # Lookup palette: [lookup_table + A]
    code.append(0xC5)                # PUSH BC
    code.extend([0x4F])              # LD C, A (tile_id in C)
    code.extend([0x06, (lookup_table_addr >> 8) & 0xFF])  # LD B, high byte of table
    # BC = 0x6Bxx where xx = tile_id
    code.append(0x0A)                # LD A, [BC]  <- palette number
    code.append(0xC1)                # POP BC

    # Write palette to dest
    code.append(0x22)                # LD [HL+], A

    # Decrement inner counter
    code.extend([0xF0, 0xC9])        # LDH A, [FFC9]
    code.append(0x3D)                # DEC A
    code.extend([0xE0, 0xC9])        # LDH [FFC9], A
    inner_offset = inner_start - len(code) - 2
    code.extend([0x20, inner_offset & 0xFF])  # JR NZ, inner_loop

    # Decrement outer counter
    code.extend([0xF0, 0xC8])        # LDH A, [FFC8]
    code.append(0x3D)                # DEC A
    code.extend([0xE0, 0xC8])        # LDH [FFC8], A
    outer_offset = outer_start - len(code) - 2
    code.extend([0x20, outer_offset & 0xFF])  # JR NZ, outer_loop

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                # RET

    return bytes(code)


def create_gdma_bg_attributes() -> bytes:
    """
    GDMA copy attribute buffer (0xD000) to VRAM BG map (0x9800) in VBK 1.

    Copies 768 bytes (48 blocks of 16 bytes).
    Must be called during VBlank.
    """
    code = bytearray()

    code.append(0xF5)                # PUSH AF

    # Switch to VRAM bank 1
    code.extend([0x3E, 0x01])        # LD A, 1
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A (VBK = 1)

    # Set up HDMA registers
    # Source: 0xD000
    code.extend([0x3E, 0xD0])        # LD A, 0xD0 (high byte)
    code.extend([0xE0, 0x51])        # LDH [HDMA1], A
    code.extend([0x3E, 0x00])        # LD A, 0x00 (low byte)
    code.extend([0xE0, 0x52])        # LDH [HDMA2], A

    # Dest: 0x9800 (BG tilemap in VRAM bank 1 = attributes)
    code.extend([0x3E, 0x98])        # LD A, 0x98 (high byte)
    code.extend([0xE0, 0x53])        # LDH [HDMA3], A
    code.extend([0x3E, 0x00])        # LD A, 0x00 (low byte)
    code.extend([0xE0, 0x54])        # LDH [HDMA4], A

    # Length: 48 blocks of 16 bytes = 768 bytes
    # HDMA5 value = (blocks - 1) = 47 = 0x2F
    # Bit 7 = 0 for general-purpose DMA (not HBlank)
    code.extend([0x3E, 0x2F])        # LD A, 0x2F (47 blocks)
    code.extend([0xE0, 0x55])        # LDH [HDMA5], A  <- starts transfer

    # Switch back to VRAM bank 0
    code.extend([0xAF])              # XOR A
    code.extend([0xE0, 0x4F])        # LDH [FF4F], A (VBK = 0)

    code.append(0xF1)                # POP AF
    code.append(0xC9)                # RET

    return bytes(code)


def create_combined_with_dma(
    palette_loader_addr: int,
    shadow_main_addr: int,
    build_bg_attr_addr: int,
    gdma_bg_attr_addr: int
) -> bytes:
    """Combined function: load palettes, colorize sprites, build BG attrs, GDMA, run sprite DMA."""
    code = bytearray()

    # Load color palettes
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])

    # Colorize sprite shadows (pre-DMA)
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])

    # Build BG attribute buffer from tiles
    code.extend([0xCD, build_bg_attr_addr & 0xFF, build_bg_attr_addr >> 8])

    # GDMA copy BG attributes to VRAM bank 1
    code.extend([0xCD, gdma_bg_attr_addr & 0xFF, gdma_bg_attr_addr >> 8])

    # Run sprite DMA (original game function)
    code.extend([0xCD, 0x80, 0xFF])  # CALL DMA

    code.append(0xC9)                # RET

    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook at 0x0824 with input handler."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v203.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v2.03: Phase 1 - Static BG Colorization ===")
    print("  Strategy:")
    print("    1. Working OBJ colorization from v1.09")
    print("    2. 256-byte tile→palette lookup table")
    print("    3. Build attribute buffer from tile buffer")
    print("    4. GDMA copy attributes to VBK 1")
    print()
    print("  Tile→Palette Mapping:")
    print("    Palette 0: Floor, platforms, default (blue)")
    print("    Palette 1: Items 0x88-0xDF (gold)")
    print("    Palette 2: Walls 0x40-0x7F (stone gray)")
    print("    Palette 3: Hazards (red)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout:
    # 0x6800-0x683F: BG palettes (64 bytes)
    # 0x6840-0x687F: OBJ palettes (64 bytes)
    # 0x6880-0x6887: Gargoyle palette (8 bytes)
    # 0x6888-0x688F: Spider palette (8 bytes)
    # 0x6890-0x68FF: Reserved
    # 0x6900: OBJ colorizer (sprite tile-based)
    # 0x6980: Shadow colorizer main
    # 0x69E0: Palette loader
    # 0x6A80: Build BG attributes
    # 0x6B00-0x6BFF: Tile→Palette lookup table (256 bytes)
    # 0x6C00: GDMA BG attributes
    # 0x6C40: Combined function

    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    build_bg_attr_addr = 0x6A80
    lookup_table_addr = 0x6B00
    gdma_bg_attr_addr = 0x6C00
    combined_addr = 0x6C40

    # Generate code
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    build_bg_attr = create_build_bg_attributes(lookup_table_addr)
    lookup_table = create_tile_palette_lookup()
    gdma_bg_attr = create_gdma_bg_attributes()
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr,
                                         build_bg_attr_addr, gdma_bg_attr_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"OBJ colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Build BG attr: {len(build_bg_attr)} bytes at 0x{build_bg_attr_addr:04X}")
    print(f"Lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")
    print(f"GDMA BG attr: {len(gdma_bg_attr)} bytes at 0x{gdma_bg_attr_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Verify no overlaps
    assert colorizer_addr + len(colorizer) <= shadow_main_addr, "OBJ colorizer overlaps shadow main"
    assert shadow_main_addr + len(shadow_main) <= palette_loader_addr, "Shadow main overlaps palette loader"
    assert palette_loader_addr + len(palette_loader) <= build_bg_attr_addr, "Palette loader overlaps build BG attr"
    assert build_bg_attr_addr + len(build_bg_attr) <= lookup_table_addr, "Build BG attr overlaps lookup table"
    assert lookup_table_addr + len(lookup_table) <= gdma_bg_attr_addr, "Lookup table overlaps GDMA"
    assert gdma_bg_attr_addr + len(gdma_bg_attr) <= combined_addr, "GDMA overlaps combined"

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def bank_offset(addr):
        return bank13_offset + (addr - 0x4000)

    # Write data
    rom[bank_offset(palette_data_addr):bank_offset(palette_data_addr) + len(bg_data)] = bg_data
    rom[bank_offset(palette_data_addr) + 64:bank_offset(palette_data_addr) + 64 + len(obj_data)] = obj_data
    rom[bank_offset(gargoyle_addr):bank_offset(gargoyle_addr) + len(gargoyle)] = gargoyle
    rom[bank_offset(spider_addr):bank_offset(spider_addr) + len(spider)] = spider

    # Write code
    rom[bank_offset(colorizer_addr):bank_offset(colorizer_addr) + len(colorizer)] = colorizer
    rom[bank_offset(shadow_main_addr):bank_offset(shadow_main_addr) + len(shadow_main)] = shadow_main
    rom[bank_offset(palette_loader_addr):bank_offset(palette_loader_addr) + len(palette_loader)] = palette_loader
    rom[bank_offset(build_bg_attr_addr):bank_offset(build_bg_attr_addr) + len(build_bg_attr)] = build_bg_attr
    rom[bank_offset(lookup_table_addr):bank_offset(lookup_table_addr) + len(lookup_table)] = lookup_table
    rom[bank_offset(gdma_bg_attr_addr):bank_offset(gdma_bg_attr_addr) + len(gdma_bg_attr)] = gdma_bg_attr
    rom[bank_offset(combined_addr):bank_offset(combined_addr) + len(combined)] = combined

    # NOP out original DMA at 0x06D5
    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    # Write VBlank hook
    print(f"VBlank hook: {len(vblank_hook)} bytes at 0x0824")
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v2.03 Build Complete ===")
    print("\nTest with:")
    print("  mgba-qt rom/working/penta_dragon_dx_FIXED.gb -t save_states_for_claude/level1_start.ss0")


if __name__ == "__main__":
    main()
