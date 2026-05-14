#!/usr/bin/env python3
"""
v1.84: BG Colorizer - proper VBK save/restore

- 8 tiles per frame, direct VBK switch per tile
- Proper row scanning based on counter
- FIX: Save/restore VBK state at start/end to avoid game corruption
- FIX: Ensure VBK=0 is restored even on early exit
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
    # tile < 0x40, default palette
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # sara_palette:
    labels['sara_palette'] = len(code)
    code.append(0x7A)                # LD A, D
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # projectile_palette:
    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # boss_palette: (boss/miniboss mode - all enemies palette 7)
    labels['boss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # hornet_palette:
    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # orc_palette:
    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])        # LD A, 5
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # humanoid_palette:
    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])        # LD A, 6
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette (placeholder)

    # miniboss_palette:
    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7
    # Falls through to apply_palette

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


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """
    Load CGB palettes with dynamic boss palette swapping.

    When boss_flag=1: Load Gargoyle into palette 6
    When boss_flag=2: Load Spider into palette 7
    Otherwise: Load normal palettes
    """
    code = bytearray()

    # Load BG palettes (64 bytes at 0xFF68/0xFF69)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])  # LD HL, bg_data
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, palette 0)
    code.extend([0xE0, 0x68])        # LDH [FF68], A (BCPS)
    code.extend([0x0E, 0x40])        # LD C, 64
    # bg_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [FF69], A (BCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, bg_loop

    # Load OBJ palettes 0-5 (48 bytes)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])  # LD HL, obj_data
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, palette 0)
    code.extend([0xE0, 0x6A])        # LDH [FF6A], A (OCPS)
    code.extend([0x0E, 0x30])        # LD C, 48 (palettes 0-5 = 6*8 bytes)
    # obj_loop1:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, obj_loop1

    # === PALETTE 6: Check for Gargoyle ===
    # HL now points to normal palette 6 data
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF] (boss flag)
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x20, 0x03])        # JR NZ, +3 (not Gargoyle)
    # Load Gargoyle address
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])  # LD HL, gargoyle
    # Load palette 6 (8 bytes) - HL already set to correct source
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal6_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal6_loop

    # === PALETTE 7: Check for Spider ===
    # Calculate normal palette 7 address
    pal7_normal_addr = obj_data_addr + 56  # 7*8 = 56 offset
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])  # LD HL, normal_pal7
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF] (boss flag)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x20, 0x03])        # JR NZ, +3 (not Spider)
    # Load Spider address
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])  # LD HL, spider
    # Load palette 7 (8 bytes)
    code.extend([0x0E, 0x08])        # LD C, 8
    # pal7_loop:
    code.extend([0x2A])              # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [FF6B], A (OCPD)
    code.extend([0x0D])              # DEC C
    code.extend([0x20, 0xFA])        # JR NZ, pal7_loop

    code.append(0xC9)                # RET
    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int) -> bytes:
    """Combined function: load palettes, colorize shadows, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # CALL DMA
    code.append(0xC9)
    return bytes(code)


def create_bg_tile_lookup_table() -> bytes:
    """256-byte lookup table: tile ID -> BG palette number."""
    table = bytearray(256)
    for i in range(256):
        table[i] = 0x00  # Default floor (blue)
        if 0xA0 <= i < 0xE0:
            table[i] = 0x01  # Items - gold
        elif 0x4C <= i < 0x50:
            table[i] = 0x05  # Hazards - red
        elif i in [0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x21, 0x22, 0x23]:
            table[i] = 0x02  # Specific walls - purple
    return bytes(table)


def create_bg_row_colorizer_lazy(lookup_table_addr: int) -> bytes:
    """BG colorizer - colorize once then stop (no continuous flickering).

    Uses two HRAM locations:
    - 0xFFC4: step counter (0-187, where 0-59=warmup, 60-187=colorize, 188+=done)
    - When counter reaches 188, stop colorizing (tilemap is done)

    This eliminates flickering by not constantly rewriting attributes.
    """
    HRAM_COUNTER = 0xC4
    WARMUP_FRAMES = 60
    TOTAL_STEPS = 128
    DONE_VALUE = WARMUP_FRAMES + TOTAL_STEPS  # 188 = done
    TILES_PER_FRAME = 8
    code = bytearray()

    # Check if LCD is on. Skip if off.
    code.extend([0xF0, 0x40])           # LDH A, [0x40]
    code.extend([0xCB, 0x7F])           # BIT 7, A
    code.append(0xC8)                   # RET Z

    # Save registers (including AF for flags)
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Save VBK state
    code.extend([0xF0, 0x4F])           # LDH A, [VBK]
    code.append(0xF5)                   # PUSH AF (save VBK on stack)

    # Read counter
    code.extend([0xF0, HRAM_COUNTER])   # LDH A, [0xFFC4]
    code.append(0x47)                   # LD B, A (save counter)

    # If counter >= DONE_VALUE (188), we're done - just restore and return
    code.extend([0xFE, DONE_VALUE])     # CP 188
    skip_if_done = len(code)
    code.extend([0x30, 0x00])           # JR NC, restore_and_ret (placeholder)

    # If counter < WARMUP, skip colorization but still increment
    code.extend([0xFE, WARMUP_FRAMES])  # CP 60
    skip_to_inc = len(code)
    code.extend([0x38, 0x00])           # JR C, just_increment (placeholder)

    # === Calculate VRAM address from counter ===
    # step = counter - WARMUP (0-127)
    code.extend([0xD6, WARMUP_FRAMES])  # SUB 60 -> A = step (0-127)
    code.append(0x4F)                   # LD C, A (save step)

    # row = step >> 2 (0-31)
    code.extend([0xCB, 0x3F])           # SRL A (step >> 1)
    code.extend([0xCB, 0x3F])           # SRL A (step >> 2)
    code.append(0x57)                   # LD D, A (D = row 0-31)

    # chunk_offset = (step & 3) * 8 = (step & 3) << 3
    code.append(0x79)                   # LD A, C (step)
    code.extend([0xE6, 0x03])           # AND 3 (chunk 0-3)
    code.extend([0xCB, 0x27])           # SLA A (x2)
    code.extend([0xCB, 0x27])           # SLA A (x4)
    code.extend([0xCB, 0x27])           # SLA A (x8) -> A = chunk_offset (0/8/16/24)
    code.append(0x5F)                   # LD E, A (E = chunk_offset)

    # Calculate: row * 32 (low byte)
    code.append(0x7A)                   # LD A, D (row)
    code.extend([0xCB, 0x27])           # SLA A (x2)
    code.extend([0xCB, 0x27])           # SLA A (x4)
    code.extend([0xCB, 0x27])           # SLA A (x8)
    code.extend([0xCB, 0x27])           # SLA A (x16)
    code.extend([0xCB, 0x27])           # SLA A (x32)
    code.append(0x83)                   # ADD E (add chunk_offset)
    code.append(0x6F)                   # LD L, A (L = low byte)

    # Calculate high byte: 0x98 + (row >> 3)
    code.append(0x7A)                   # LD A, D (row)
    code.extend([0xCB, 0x3F])           # SRL A (row >> 1)
    code.extend([0xCB, 0x3F])           # SRL A (row >> 2)
    code.extend([0xCB, 0x3F])           # SRL A (row >> 3) -> A = 0-3
    code.extend([0xC6, 0x98])           # ADD 0x98 -> A = 0x98-0x9B
    code.append(0x67)                   # LD H, A

    # HL now points to correct VRAM address for this frame's 8 tiles
    # D = loop counter
    code.extend([0x16, TILES_PER_FRAME])  # LD D, 8

    # Main loop: for each tile, read VBK0, lookup, write VBK1
    main_loop = len(code)

    # Save HL (VRAM pos) on stack
    code.append(0xE5)                   # PUSH HL

    # VBK = 0 for reading tile ID
    code.extend([0xAF])                 # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Read tile ID from VRAM
    code.append(0x7E)                   # LD A, [HL]

    # Lookup palette: HL = lookup_table + tile_id
    code.append(0x6F)                   # LD L, A (tile ID as low byte)
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])  # LD H, high byte of table
    code.append(0x7E)                   # LD A, [HL] = palette for this tile
    code.append(0x5F)                   # LD E, A (save palette)

    # VBK = 1 for writing attribute
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Restore HL (VRAM pos from stack), write palette as attribute
    code.append(0xE1)                   # POP HL
    code.append(0x7B)                   # LD A, E (palette)
    code.append(0x77)                   # LD [HL], A (write to VRAM bank 1)

    # Next tile
    code.append(0x23)                   # INC HL
    code.append(0x15)                   # DEC D
    offset = main_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])  # JR NZ, main_loop

    # just_increment: increment counter (don't wrap - let it stay at 188 when done)
    just_inc_label = len(code)
    code[skip_to_inc + 1] = (just_inc_label - skip_to_inc - 2) & 0xFF

    code.append(0x78)                   # LD A, B (original counter)
    code.append(0x3C)                   # INC A
    code.extend([0xE0, HRAM_COUNTER])   # LDH [0xFFC4], A

    # restore_and_ret: restore VBK and registers
    restore_label = len(code)
    code[skip_if_done + 1] = (restore_label - skip_if_done - 2) & 0xFF

    code.append(0xF1)                   # POP AF (restore VBK value)
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)
    return bytes(code)

def create_bg_row_colorizer_lazy_FULL(lookup_table_addr: int) -> bytes:
    """BG colorizer - only 8 tiles per frame, with gameplay detection."""
    WRAM_BUFFER = 0xD900  # Changed from 0xDFF0 (safer location)
    HRAM_COUNTER = 0xC4   # Changed from 0xC0 (0xFFC0 may conflict with game)
    TILES_PER_FRAME = 8   # Only 8 tiles per frame (was 32)
    WARMUP_FRAMES = 60
    # 32 tiles per row / 8 tiles per frame = 4 frames per row
    # 32 rows * 4 = 128 steps total
    TOTAL_STEPS = 128
    code = bytearray()

    # Check if LCD is on. Skip if off.
    code.extend([0xF0, 0x40])           # LDH A, [0x40]
    code.extend([0xCB, 0x7F])           # BIT 7, A
    code.append(0xC8)                   # RET Z

    # Sara check REMOVED - was reading hardware OAM and may cause freeze
    # Will colorize title screen too, but at least gameplay will work

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Read counter
    code.extend([0xF0, HRAM_COUNTER])   # LDH A, [0xFFC4]
    code.append(0x47)                   # LD B, A (save counter)

    # If counter < WARMUP, just increment and return
    code.extend([0xFE, WARMUP_FRAMES])
    skip_to_end = len(code)
    code.extend([0x38, 0x00])           # JR C, end (placeholder)

    # Calculate step = counter - WARMUP
    code.extend([0xD6, WARMUP_FRAMES])  # SUB warmup
    # step is now 0-127
    # row = step / 4 = step >> 2
    # chunk = step & 3 (0-3, which chunk of 8 tiles)
    code.append(0x4F)                   # LD C, A (save step)

    # Calculate row = step >> 2
    code.append(0x0F)                   # RRCA
    code.append(0x0F)                   # RRCA
    code.extend([0xE6, 0x1F])           # AND 0x1F (row 0-31)
    code.append(0x57)                   # LD D, A (save row)

    # Calculate chunk offset = (step & 3) * 8
    code.append(0x79)                   # LD A, C (step)
    code.extend([0xE6, 0x03])           # AND 3 (chunk 0-3)
    code.append(0x87)                   # ADD A (x2)
    code.append(0x87)                   # ADD A (x4)
    code.append(0x87)                   # ADD A (x8)
    code.append(0x5F)                   # LD E, A (chunk offset 0/8/16/24)

    # Calculate VRAM address: 0x9800 + row * 32 + chunk_offset
    code.append(0x7A)                   # LD A, D (row)
    code.append(0x87)                   # x2
    code.append(0x87)                   # x4
    code.append(0x87)                   # x8
    code.append(0x87)                   # x16
    code.append(0x87)                   # x32
    code.append(0x83)                   # ADD E (add chunk offset)
    code.append(0x6F)                   # LD L, A
    code.extend([0x26, 0x98])           # LD H, 0x98
    code.append(0x7A)                   # LD A, D (row)
    code.extend([0xE6, 0x18])           # AND 0x18
    code.append(0x0F)
    code.append(0x0F)
    code.append(0x0F)
    code.append(0x84)                   # ADD H
    code.append(0x67)                   # LD H, A

    # Save original VBK in C, then set VBK=0 for tile reading
    code.extend([0xF0, 0x4F])           # LDH A, [0xFF4F]
    code.append(0x4F)                   # LD C, A (save VBK)
    code.extend([0xAF])                 # XOR A (A = 0)
    code.extend([0xE0, 0x4F])           # LDH [0xFF4F], A (VBK = 0)

    code.append(0xE5)                   # PUSH HL (save VRAM addr)

    # Phase 1: Read 8 tiles from VBK=0, lookup palettes, store in WRAM
    code.extend([0x11, WRAM_BUFFER & 0xFF, (WRAM_BUFFER >> 8) & 0xFF])
    code.extend([0x3E, TILES_PER_FRAME])
    code.append(0x57)                   # LD D, 8 (loop counter)

    read_loop = len(code)
    code.append(0x7E)                   # LD A, [HL]
    code.append(0xE5)                   # PUSH HL
    code.append(0x6F)                   # LD L, A
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])
    code.append(0x7E)                   # LD A, [HL]
    code.append(0xE1)                   # POP HL
    code.append(0x12)                   # LD [DE], A
    code.append(0x13)                   # INC DE
    code.append(0x23)                   # INC HL
    code.append(0x15)                   # DEC D
    offset = read_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # Phase 2: VBK=1 and write 8 attributes
    code.extend([0x3E, 0x01])
    code.extend([0xE0, 0x4F])           # VBK = 1
    code.append(0xE1)                   # POP HL
    code.extend([0x11, WRAM_BUFFER & 0xFF, (WRAM_BUFFER >> 8) & 0xFF])
    code.extend([0x3E, TILES_PER_FRAME])
    code.append(0x57)                   # LD D, 8

    write_loop = len(code)
    code.append(0x1A)                   # LD A, [DE]
    code.append(0x77)                   # LD [HL], A
    code.append(0x13)                   # INC DE
    code.append(0x23)                   # INC HL
    code.append(0x15)                   # DEC D
    offset = write_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # Restore VBK from C
    code.append(0x79)                   # LD A, C
    code.extend([0xE0, 0x4F])           # LDH [0xFF4F], A

    # end: increment counter
    end_label = len(code)
    code[skip_to_end + 1] = (end_label - skip_to_end - 2) & 0xFF

    code.append(0x78)                   # LD A, B
    code.append(0x3C)                   # INC A
    wrap_val = WARMUP_FRAMES + TOTAL_STEPS
    code.extend([0xFE, wrap_val])       # CP wrap_val (60+128=188)
    code.extend([0x38, 0x02])           # JR C, +2
    code.extend([0x3E, WARMUP_FRAMES])  # LD A, warmup
    code.extend([0xE0, HRAM_COUNTER])   # LDH [0xFFC4], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_combined_with_dma_and_bg(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined: palettes, sprite colorize, BG colorize, DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
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
    output_rom = Path("rom/working/penta_dragon_dx_v184.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.84: Colorize once, VBK save/restore ===")
    print("  8 tiles/frame, colorizes tilemap ONCE then stops")
    print("  Saves/restores VBK state to avoid game corruption")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout - same as v1.09 plus BG colorizer + lookup table
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    bg_colorizer_addr = 0x6A40
    combined_addr = 0x6AA8  # Moved to fit bg_colorizer (~96 bytes)
    lookup_table_addr = 0x6B00

    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_colorizer = create_bg_row_colorizer_lazy(lookup_table_addr)
    lookup_table = create_bg_tile_lookup_table()
    combined = create_combined_with_dma_and_bg(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"Lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    # Write palette data
    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    # Write boss palettes
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    # Write code
    rom[bank13_offset + (colorizer_addr - 0x4000):bank13_offset + (colorizer_addr - 0x4000) + len(colorizer)] = colorizer
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (bg_colorizer_addr - 0x4000):bank13_offset + (bg_colorizer_addr - 0x4000) + len(bg_colorizer)] = bg_colorizer
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined
    rom[bank13_offset + (lookup_table_addr - 0x4000):bank13_offset + (lookup_table_addr - 0x4000) + len(lookup_table)] = lookup_table

    # NOP out DMA at 0x06D5
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])

    # Write VBlank hook
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.84 Build Complete ===")


if __name__ == "__main__":
    main()
