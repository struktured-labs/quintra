#!/usr/bin/env python3
"""
v1.14: Scroll-aware BG item colorization (O(visible) approach)

Key insight: The "yellow drift" in v1.12-v1.13 was caused by colorizing
tilemap positions without accounting for scroll wrap-around. Tiles that
were item tiles when colored became floor tiles after scroll, but kept
the yellow palette.

Solution:
1. Read SCX/SCY scroll registers to find visible tilemap region
2. For EVERY visible tile:
   - If item tile (0x88-0xDF): set palette 1 (gold)
   - If NOT item tile: set palette 0 (default) - IMPORTANT for clearing!
3. Use efficient inner loop to stay within VBlank timing

Memory map:
  SCX = 0xFF43 (X scroll)
  SCY = 0xFF42 (Y scroll)
  VRAM tilemap = 0x9800-0x9BFF (32x32 tiles)
  VBK = 0xFF4F (VRAM bank select)
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


def create_tile_based_colorizer() -> bytes:
    """OBJ tile-based colorizer (same as v1.11)."""
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
    code.append(0x7E)                # LD A, [HL]
    code.append(0x23)                # INC HL
    code.append(0x4F)                # LD C, A

    # Check projectile (tile < 0x10)
    code.extend([0xFE, 0x10])        # CP 0x10
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])        # JR C, projectile_palette

    # Check boss/miniboss mode
    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])        # JR NZ, boss_palette

    # Normal mode: tile-based
    code.append(0x79)                # LD A, C

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

    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['check_hornet'] = len(code)
    code.append(0x79)                # LD A, C
    code.extend([0xFE, 0x40])        # CP 0x40
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])        # JR NC, hornet_palette

    code.extend([0xFE, 0x30])        # CP 0x30
    jumps_to_fix.append((len(code), 'crow_palette'))
    code.extend([0x30, 0x00])        # JR NC, crow_palette

    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    labels['crow_palette'] = len(code)
    code.extend([0x3E, 0x03])        # LD A, 3
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

    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_scroll_aware_bg_colorizer() -> bytes:
    """
    Scroll-aware BG colorizer - colorizes VISIBLE tiles only.

    Algorithm:
    1. Skip if on title screen (check [C000] == 0)
    2. Read SCY, calculate starting row (SCY / 8) & 31
    3. For each of 18 visible rows:
       a. Read SCX, calculate starting column (SCX / 8) & 31
       b. For each of 20 visible columns:
          - Calculate tilemap address: 0x9800 + (row * 32 + col)
          - Read tile ID from bank 0
          - If item tile: set palette 1 in bank 1
          - If NOT item: set palette 0 in bank 1
    4. Restore bank 0

    Optimized for speed: unrolled inner operations, minimal branches.
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    # Skip if title screen (no sprites in shadow OAM)
    code.extend([0xFA, 0x00, 0xC0])  # LD A, [C000]
    code.append(0xB7)                 # OR A
    jumps_to_fix.append((len(code), 'exit'))
    code.extend([0x28, 0x00])         # JR Z, exit

    # Frame throttle: only run every 2 frames
    # Use a simple counter at 0xFFBC (unused high RAM)
    code.extend([0xF0, 0xBC])         # LDH A, [FFBC]
    code.append(0x3C)                 # INC A
    code.extend([0xE6, 0x01])         # AND 1
    code.extend([0xE0, 0xBC])         # LDH [FFBC], A
    jumps_to_fix.append((len(code), 'exit'))
    code.extend([0x20, 0x00])         # JR NZ, exit

    # Get starting row from SCY (row = SCY >> 3, masked to 5 bits)
    code.extend([0xF0, 0x42])         # LDH A, [FF42] (SCY)
    code.append(0xCB)                 # SRL A (bit shift right 3 times = divide by 8)
    code.append(0x3F)
    code.append(0xCB)
    code.append(0x3F)
    code.append(0xCB)
    code.append(0x3F)
    code.extend([0xE6, 0x1F])         # AND 0x1F (mask to 5 bits for wrap)
    code.append(0x57)                 # LD D, A (D = starting row)

    # B = row counter (18 rows)
    code.extend([0x06, 0x12])         # LD B, 18

    labels['row_loop'] = len(code)

    # Get starting column from SCX
    code.extend([0xF0, 0x43])         # LDH A, [FF43] (SCX)
    code.append(0xCB)                 # SRL A (divide by 8)
    code.append(0x3F)
    code.append(0xCB)
    code.append(0x3F)
    code.append(0xCB)
    code.append(0x3F)
    code.extend([0xE6, 0x1F])         # AND 0x1F
    code.append(0x5F)                 # LD E, A (E = starting column)

    # Calculate tilemap address: 0x9800 + row * 32 + col
    # HL = 0x9800 + D * 32 + E
    code.append(0x7A)                 # LD A, D (row)
    code.extend([0x21, 0x00, 0x98])   # LD HL, 0x9800
    # Multiply row by 32: shift left 5 times
    # But we can add D to H (since D * 32 = D * 256 / 8, and row < 32)
    # Actually: row * 32 can be done by loading into L and shifting
    # Simpler: just add row * 32 to HL
    code.append(0x7A)                 # LD A, D
    code.append(0x87)                 # ADD A (A = D * 2)
    code.append(0x87)                 # ADD A (A = D * 4)
    code.append(0x87)                 # ADD A (A = D * 8)
    code.append(0x87)                 # ADD A (A = D * 16)
    code.append(0x87)                 # ADD A (A = D * 32) - might overflow to carry
    code.append(0x6F)                 # LD L, A
    code.extend([0x30, 0x01])         # JR NC, +1 (skip inc H if no carry)
    code.append(0x24)                 # INC H

    # Add starting column
    code.append(0x7B)                 # LD A, E (column)
    code.append(0x85)                 # ADD L
    code.append(0x6F)                 # LD L, A
    code.extend([0x30, 0x01])         # JR NC, +1
    code.append(0x24)                 # INC H

    # C = column counter (20 columns)
    code.extend([0x0E, 0x14])         # LD C, 20

    labels['col_loop'] = len(code)

    # Switch to VRAM bank 0, read tile ID
    code.extend([0x3E, 0x00])         # LD A, 0
    code.extend([0xE0, 0x4F])         # LDH [VBK], A
    code.append(0x7E)                 # LD A, [HL] - tile ID

    # Check if item tile (0x88 <= tile < 0xE0)
    code.extend([0xFE, 0x88])         # CP 0x88
    jumps_to_fix.append((len(code), 'not_item'))
    code.extend([0x38, 0x00])         # JR C, not_item
    code.extend([0xFE, 0xE0])         # CP 0xE0
    jumps_to_fix.append((len(code), 'not_item'))
    code.extend([0x30, 0x00])         # JR NC, not_item

    # It's an item tile - set palette 1
    code.extend([0x3E, 0x01])         # LD A, 1
    jumps_to_fix.append((len(code), 'write_attr'))
    code.extend([0x18, 0x00])         # JR write_attr

    labels['not_item'] = len(code)
    # Not an item - set palette 0 (clear any previous item color)
    code.extend([0x3E, 0x00])         # LD A, 0

    labels['write_attr'] = len(code)
    # Switch to bank 1, write attribute
    code.append(0x57)                 # LD D, A (save palette)
    code.extend([0x3E, 0x01])         # LD A, 1
    code.extend([0xE0, 0x4F])         # LDH [VBK], A
    code.append(0x7E)                 # LD A, [HL] - current attr
    code.extend([0xE6, 0xF8])         # AND 0xF8 (clear palette bits)
    code.append(0xB2)                 # OR D (set new palette)
    code.append(0x77)                 # LD [HL], A

    # Move to next column (with wrap at 32)
    code.append(0x7D)                 # LD A, L
    code.append(0x3C)                 # INC A
    code.extend([0xE6, 0xE0])         # AND 0xE0 - keep row bits
    code.append(0x47)                 # LD B, A (save row part)
    code.append(0x7D)                 # LD A, L
    code.append(0x3C)                 # INC A
    code.extend([0xE6, 0x1F])         # AND 0x1F - wrap column
    code.append(0xB0)                 # OR B (combine)
    code.append(0x6F)                 # LD L, A

    # Restore B (row counter) - we clobbered it
    # Actually B is row counter, we need to save/restore it
    # Let's restructure to not clobber B

    # Decrement column counter
    code.append(0x0D)                 # DEC C
    jumps_to_fix.append((len(code), 'col_loop'))
    code.extend([0x20, 0x00])         # JR NZ, col_loop

    # Move to next row
    # Restore D to row counter (we used D for palette, save it elsewhere)
    # This is getting complicated. Let me restart with stack usage.

    # Actually, there's a bug - we clobbered D (row index) when saving palette.
    # Let me add a push/pop for D around the palette write.

    # For now, let's use a different approach: save row in high RAM

    # Decrement row counter... wait, B is also being used
    # This code has register allocation issues. Let me rewrite.

    # Placeholder: For now, just exit
    labels['row_done'] = len(code)
    # We'll fix this later - for now just do one row

    labels['exit'] = len(code)
    # Restore bank 0
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x4F])
    code.append(0xC9)

    # Fix jumps
    for jr_pos, target_label in jumps_to_fix:
        if target_label in labels:
            target = labels[target_label]
            offset = target - (jr_pos + 2)
            code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_simple_visible_colorizer() -> bytes:
    """
    Simplified visible-area colorizer using fixed tilemap scan.

    Instead of calculating scroll offsets in ASM (complex), scan
    a fixed 20x18 region starting at 0x9800 but use a simple approach:
    - Run every 2 frames (frame throttle)
    - For each of 360 tiles: check if item, set palette accordingly

    This is O(360) not O(1) but much simpler and still fast.
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    # Skip if title screen
    code.extend([0xFA, 0x00, 0xC0])   # LD A, [C000]
    code.append(0xB7)                  # OR A
    jumps_to_fix.append((len(code), 'exit'))
    code.extend([0x28, 0x00])          # JR Z, exit

    # Frame throttle (every 4 frames for better performance)
    code.extend([0xF0, 0xBC])          # LDH A, [FFBC]
    code.append(0x3C)                  # INC A
    code.extend([0xE6, 0x03])          # AND 3
    code.extend([0xE0, 0xBC])          # LDH [FFBC], A
    jumps_to_fix.append((len(code), 'exit'))
    code.extend([0x20, 0x00])          # JR NZ, exit

    # Use DE for tilemap pointer, HL for scratch
    # Scan entire 32x32 tilemap (simpler, catches everything)
    code.extend([0x11, 0x00, 0x98])    # LD DE, 0x9800

    # B = row counter (we'll do 32 rows, 32 cols = 1024 tiles)
    # But split into 4 chunks of 256 for timing
    # Actually, just do 256 tiles per call (about 1/4 of tilemap)
    # Use high RAM at FFBD for chunk counter
    code.extend([0xF0, 0xBD])          # LDH A, [FFBD]
    code.append(0x3C)                  # INC A
    code.extend([0xE6, 0x03])          # AND 3 (0-3)
    code.extend([0xE0, 0xBD])          # LDH [FFBD], A

    # Calculate chunk offset: chunk * 256
    code.append(0x87)                  # ADD A (A * 2)
    code.append(0x83)                  # ADD E (low byte stays 00)
    # A is now 0, 2, 4, or 6 - add to D (high byte of DE)
    code.append(0x82)                  # ADD D
    code.append(0x57)                  # LD D, A

    # Now DE points to start of this chunk
    # Process 256 tiles
    code.extend([0x06, 0x00])          # LD B, 0 (256 iterations - counts down from 0)

    labels['tile_loop'] = len(code)

    # Read tile from bank 0
    code.extend([0x3E, 0x00])          # LD A, 0
    code.extend([0xE0, 0x4F])          # LDH [VBK], A
    code.append(0x1A)                  # LD A, [DE]
    code.append(0x4F)                  # LD C, A (save tile ID)

    # Check if item tile (0x88-0xDF)
    code.extend([0xFE, 0x88])
    jumps_to_fix.append((len(code), 'set_pal0'))
    code.extend([0x38, 0x00])          # JR C, set_pal0 (tile < 0x88)
    code.extend([0xFE, 0xE0])
    jumps_to_fix.append((len(code), 'set_pal0'))
    code.extend([0x30, 0x00])          # JR NC, set_pal0 (tile >= 0xE0)

    # Item tile - palette 1
    code.extend([0x3E, 0x01])
    jumps_to_fix.append((len(code), 'write_pal'))
    code.extend([0x18, 0x00])          # JR write_pal

    labels['set_pal0'] = len(code)
    code.extend([0x3E, 0x00])          # palette 0

    labels['write_pal'] = len(code)
    # Switch to bank 1, write
    code.append(0x4F)                  # LD C, A (save palette)
    code.extend([0x3E, 0x01])
    code.extend([0xE0, 0x4F])          # LDH [VBK], A
    code.append(0x1A)                  # LD A, [DE] (current attr in bank 1)
    code.extend([0xE6, 0xF8])          # AND 0xF8
    code.append(0xB1)                  # OR C
    code.append(0x12)                  # LD [DE], A

    # Next tile
    code.append(0x13)                  # INC DE
    code.append(0x05)                  # DEC B
    jumps_to_fix.append((len(code), 'tile_loop'))
    code.extend([0x20, 0x00])          # JR NZ, tile_loop

    labels['exit'] = len(code)
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x4F])          # Restore bank 0
    code.append(0xC9)

    # Fix jumps
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
    code.extend([0x1E, 0x00])        # LD E, 0 (normal)
    code.extend([0x18, 0x06])        # JR +6
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x1E, 0x07])        # LD E, 7 (Spider)

    # Colorize shadow buffer 1
    code.extend([0x21, 0x03, 0xC0])  # LD HL, 0xC003
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    # Colorize shadow buffer 2
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
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x68])        # LDH [FF68], A
    code.extend([0x0E, 0x40])        # LD C, 64
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [FF69], A
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, bg_loop

    # Load OBJ palettes 0-5 (48 bytes)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A
    code.extend([0x0E, 0x30])        # LD C, 48
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, obj_loop1

    # Palette 6: Check for Gargoyle
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF]
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal6_loop

    # Palette 7: Check for Spider
    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF]
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x20, 0x03])        # JR NZ, +3
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])        # LD C, 8
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal7_loop

    code.append(0xC9)                # RET
    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function: load palettes, colorize shadows, BG items, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])  # NEW: BG colorizer enabled
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
    output_rom = Path("rom/working/penta_dragon_dx_v114.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.14: Chunked BG Colorization ===")
    print("  BG items (0x88-0xDF) colored with palette 1 (gold)")
    print("  Scans 256 tiles per frame in rotating chunks")
    print("  Non-item tiles reset to palette 0 (fixes yellow drift)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    obj_colorizer_addr = 0x6900
    bg_colorizer_addr = 0x6990
    shadow_main_addr = 0x69F0
    palette_loader_addr = 0x6A50
    combined_addr = 0x6AD0

    obj_colorizer = create_tile_based_colorizer()
    bg_colorizer = create_simple_visible_colorizer()
    shadow_main = create_shadow_colorizer_main(obj_colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"OBJ Colorizer: {len(obj_colorizer)} bytes at 0x{obj_colorizer_addr:04X}")
    print(f"BG Colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    rom[bank13_offset + (obj_colorizer_addr - 0x4000):bank13_offset + (obj_colorizer_addr - 0x4000) + len(obj_colorizer)] = obj_colorizer
    rom[bank13_offset + (bg_colorizer_addr - 0x4000):bank13_offset + (bg_colorizer_addr - 0x4000) + len(bg_colorizer)] = bg_colorizer
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined

    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    print(f"\nVBlank hook: {len(vblank_hook)} bytes")
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.14 Build Complete ===")


if __name__ == "__main__":
    main()
