#!/usr/bin/env python3
"""
v1.37: HDMA-Based BG Colorization

Key insight: Use GBC's HDMA hardware for automatic attribute transfer.
- Build attribute buffer in WRAM during VBlank
- HDMA transfers 16 bytes per HBlank automatically
- Hardware-managed timing, no CPU cycles during HBlank transfer

HDMA Registers:
- 0xFF51/52: Source high/low (WRAM buffer)
- 0xFF53/54: Destination high/low (VRAM, only bits 12-4 used)
- 0xFF55: Length/mode - bit 7=HBlank mode, bits 0-6=blocks-1 (16 bytes each)

Strategy:
- Frame 1: Process rows 0-7 (256 tiles), start HDMA
- Frame 2: Process rows 8-15, start HDMA
- Frame 3: Process rows 16-23, start HDMA
- Frame 4: Process rows 24-31, start HDMA
- Cycle repeats - full tilemap updated every 4 frames
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
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
    """Create 256-byte lookup table: tile_id -> palette number."""
    lookup = bytearray(256)
    for i in range(256):
        if 0x40 <= i < 0x80:
            lookup[i] = 2  # Walls -> purple
        elif 0x80 <= i < 0xA0:
            lookup[i] = 3  # Hazards -> green
        elif 0xA0 <= i < 0xE0:
            lookup[i] = 1  # Items -> gold
        else:
            lookup[i] = 0  # Floor/default
    return bytes(lookup)


def create_tile_based_colorizer() -> bytes:
    """Sprite colorizer - MUST BE AT 0x6C00."""
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    code.extend([0x06, 0x28])
    labels['loop_start'] = len(code)

    code.extend([0x3E, 0x28])
    code.append(0x90)
    code.extend([0xFE, 0x04])
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])

    code.append(0x2B)
    code.append(0x7E)
    code.append(0x23)
    code.append(0x4F)

    code.extend([0xFE, 0x10])
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])

    code.append(0x7B)
    code.append(0xB7)
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])

    code.append(0x79)
    code.extend([0xFE, 0x50])
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x60])
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x70])
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x80])
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])

    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['check_hornet'] = len(code)
    code.append(0x79)
    code.extend([0xFE, 0x40])
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['sara_palette'] = len(code)
    code.append(0x7A)
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['boss_palette'] = len(code)
    code.extend([0x3E, 0x07])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])

    labels['apply_palette'] = len(code)
    code.append(0x4F)
    code.append(0x7E)
    code.extend([0xE6, 0xF8])
    code.append(0xB1)
    code.append(0x77)

    code.extend([0x23, 0x23, 0x23, 0x23])
    code.append(0x05)
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])
    code.append(0xC9)

    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """Colorizes BOTH shadow buffers."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    code.extend([0xF0, 0xBE])
    code.append(0xB7)
    code.extend([0x20, 0x04])
    code.extend([0x16, 0x02])
    code.extend([0x18, 0x02])
    code.extend([0x16, 0x01])

    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x28, 0x08])
    code.extend([0xFE, 0x02])
    code.extend([0x28, 0x06])
    code.extend([0x1E, 0x00])
    code.extend([0x18, 0x06])
    code.extend([0x1E, 0x06])
    code.extend([0x18, 0x02])
    code.extend([0x1E, 0x07])

    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)
    return bytes(code)


def create_hdma_bg_colorizer(lookup_table_addr: int, attr_buffer_addr: int,
                              row_counter_addr: int) -> bytes:
    """
    HDMA-based BG colorizer.

    Each frame:
    1. Read which 8-row chunk to process (0-3)
    2. Read 256 tiles from VRAM bank 0
    3. Lookup palettes, store in WRAM buffer
    4. Switch to VRAM bank 1
    5. Start HDMA transfer
    6. Increment row counter (mod 4)

    HDMA will transfer 256 bytes (16 bytes * 16 blocks) during HBlanks.
    Full screen updated every 4 frames.
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Get current row chunk (0-3) from HRAM
    code.extend([0xF0, row_counter_addr & 0xFF])  # LDH A, [row_counter]
    code.extend([0xE6, 0x03])  # AND 3 (wrap to 0-3)
    code.append(0x47)  # LD B, A (save chunk number)

    # Calculate tilemap start address: 0x9800 + chunk * 256
    # chunk 0: 0x9800, chunk 1: 0x9900, chunk 2: 0x9A00, chunk 3: 0x9B00
    code.append(0x87)  # ADD A, A (chunk * 2)
    code.append(0x87)  # ADD A, A (chunk * 4)
    code.append(0x87)  # ADD A, A (chunk * 8)
    code.append(0x87)  # ADD A, A (chunk * 16)
    code.append(0x87)  # ADD A, A (chunk * 32)
    code.append(0x87)  # ADD A, A (chunk * 64)
    code.append(0x87)  # ADD A, A (chunk * 128)
    code.append(0x87)  # ADD A, A (chunk * 256)
    # Now A = 0x00, 0x01, 0x02, or 0x03 (high byte offset)
    code.extend([0xC6, 0x98])  # ADD A, 0x98
    code.append(0x67)  # LD H, A
    code.extend([0x2E, 0x00])  # LD L, 0
    # Now HL = 0x9800 + chunk * 256

    # Ensure VRAM bank 0
    code.extend([0x3E, 0x00])  # LD A, 0
    code.extend([0xE0, 0x4F])  # LDH [VBK], A

    # DE = attribute buffer in WRAM
    code.extend([0x11, attr_buffer_addr & 0xFF, (attr_buffer_addr >> 8) & 0xFF])

    # C = lookup table high byte
    code.extend([0x0E, (lookup_table_addr >> 8) & 0xFF])

    # Process 256 tiles (8 rows * 32 tiles)
    # Use two nested loops: outer=8 rows, inner=32 tiles
    code.extend([0x3E, 0x08])  # LD A, 8 (outer loop)
    code.append(0xF5)  # PUSH AF (save outer counter)

    outer_loop = len(code)
    code.extend([0x06, 0x20])  # LD B, 32 (inner loop)

    inner_loop = len(code)
    # Read tile ID from VRAM
    code.append(0x7E)  # LD A, [HL]
    code.append(0x23)  # INC HL

    # Lookup palette: lookup_table[tile_id]
    code.append(0xE5)  # PUSH HL
    code.append(0x6F)  # LD L, A (tile ID as low byte)
    code.append(0x61)  # LD H, C (lookup table high byte)
    code.append(0x7E)  # LD A, [HL] (palette number)
    code.append(0xE1)  # POP HL

    # Store palette in buffer
    code.append(0x12)  # LD [DE], A
    code.append(0x13)  # INC DE

    # Inner loop
    code.append(0x05)  # DEC B
    code.extend([0x20, (inner_loop - len(code) - 2) & 0xFF])

    # Outer loop
    code.append(0xF1)  # POP AF
    code.append(0x3D)  # DEC A
    code.extend([0x28, 0x03])  # JR Z, skip_push
    code.append(0xF5)  # PUSH AF
    code.extend([0x18, (outer_loop - len(code) - 2) & 0xFF])
    # skip_push falls through

    # Now attribute buffer is filled with 256 palette values

    # Calculate HDMA destination address (same as source tilemap chunk)
    code.append(0x78)  # LD A, B (restore chunk - wait, B was used)
    # Actually need to recalculate from row_counter
    code.extend([0xF0, row_counter_addr & 0xFF])  # LDH A, [row_counter]
    code.extend([0xE6, 0x03])  # AND 3
    code.append(0x87)  # ADD A, A (*2)
    code.append(0x87)  # ADD A, A (*4)
    code.append(0x87)  # ADD A, A (*8)
    code.append(0x87)  # ADD A, A (*16)
    code.append(0x87)  # ADD A, A (*32)
    code.append(0x87)  # ADD A, A (*64)
    code.append(0x87)  # ADD A, A (*128)
    code.append(0x87)  # ADD A, A (*256)
    code.extend([0xC6, 0x98])  # ADD A, 0x98
    code.append(0x57)  # LD D, A (dest high byte = 0x98-0x9B)
    code.extend([0x1E, 0x00])  # LD E, 0 (dest low byte)

    # Switch to VRAM bank 1 (for attribute writes)
    code.extend([0x3E, 0x01])  # LD A, 1
    code.extend([0xE0, 0x4F])  # LDH [VBK], A

    # Set up HDMA registers
    # Source = attr_buffer_addr (WRAM)
    code.extend([0x3E, (attr_buffer_addr >> 8) & 0xFF])  # Source high
    code.extend([0xE0, 0x51])  # LDH [HDMA1], A
    code.extend([0x3E, attr_buffer_addr & 0xFF])  # Source low
    code.extend([0xE0, 0x52])  # LDH [HDMA2], A

    # Destination = VRAM (D:E from above, but only high nibble of high byte used)
    code.append(0x7A)  # LD A, D (dest high = 0x98-0x9B)
    code.extend([0xE0, 0x53])  # LDH [HDMA3], A
    code.extend([0x3E, 0x00])  # Dest low = 0x00
    code.extend([0xE0, 0x54])  # LDH [HDMA4], A

    # Start HDMA: 256 bytes = 16 blocks, so length = 16-1 = 0x0F
    # Bit 7 = 1 for HBlank DMA mode
    code.extend([0x3E, 0x8F])  # LD A, 0x8F (HBlank mode + 15 = 16 blocks)
    code.extend([0xE0, 0x55])  # LDH [HDMA5], A - starts transfer!

    # Switch back to VRAM bank 0
    code.extend([0x3E, 0x00])  # LD A, 0
    code.extend([0xE0, 0x4F])  # LDH [VBK], A

    # Increment row counter for next frame
    code.extend([0xF0, row_counter_addr & 0xFF])  # LDH A, [row_counter]
    code.append(0x3C)  # INC A
    code.extend([0xE0, row_counter_addr & 0xFF])  # LDH [row_counter], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_onetime_init(init_done_flag: int) -> bytes:
    """Hybrid palette initialization."""
    code = bytearray()

    # BG palettes
    code.extend([0x3E, 0x80])  # LD A, 0x80 (auto-increment)
    code.extend([0xE0, 0x68])  # LDH [BCPS], A

    # Hardcode first palette (8 bytes)
    for _ in range(8):
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    # Loop for remaining 56 bytes
    code.extend([0x06, 0x38])  # LD B, 56
    code.append(0xAF)          # XOR A
    bg_loop = len(code)
    code.extend([0xE0, 0x69])  # LDH [BCPD], A
    code.append(0x05)          # DEC B
    code.extend([0x20, (bg_loop - len(code) - 2) & 0xFF])

    # OBJ palettes
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])

    # Hardcode first palette
    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0xFF]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x7F]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x94]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x52]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x08]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x21]); code.extend([0xE0, 0x6B])

    # Loop for remaining 7 palettes
    code.extend([0x06, 0x07])
    obj_loop = len(code)
    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0xFF]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x7F]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x94]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x52]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x08]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x21]); code.extend([0xE0, 0x6B])
    code.append(0x05)
    code.extend([0x20, (obj_loop - len(code) - 2) & 0xFF])

    code.extend([0x3E, 0x01])
    code.extend([0xE0, init_done_flag & 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_fast_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int,
                                init_routine_addr: int, init_done_flag: int) -> bytes:
    """Fast palette loader with one-time init check."""
    code = bytearray()

    code.extend([0xF0, init_done_flag & 0xFF])
    code.append(0xB7)
    code.extend([0x20, 0x03])
    code.extend([0xCD, init_routine_addr & 0xFF, init_routine_addr >> 8])

    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x0E, 0x40])
    loop1_start = len(code)
    code.append(0x2A)
    code.extend([0xE0, 0x69])
    code.append(0x0D)
    code.extend([0x20, (loop1_start - len(code) - 2) & 0xFF])

    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x30])
    loop2_start = len(code)
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x0D)
    code.extend([0x20, (loop2_start - len(code) - 2) & 0xFF])

    pal6_normal_addr = obj_data_addr + 48
    code.extend([0x21, pal6_normal_addr & 0xFF, (pal6_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    loop3_start = len(code)
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x0D)
    code.extend([0x20, (loop3_start - len(code) - 2) & 0xFF])

    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x03])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    loop4_start = len(code)
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x0D)
    code.extend([0x20, (loop4_start - len(code) - 2) & 0xFF])

    code.append(0xC9)
    return bytes(code)


def create_combined_with_hdma(palette_loader_addr: int, shadow_main_addr: int,
                               hdma_colorizer_addr: int) -> bytes:
    """Combined function with HDMA BG colorization."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, hdma_colorizer_addr & 0xFF, hdma_colorizer_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
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
    output_rom = Path("rom/working/penta_dragon_dx_v137.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.37: HDMA-Based BG Colorization ===")
    print("  Uses HDMA hardware for automatic attribute transfer")
    print("  256 tiles per frame (8 rows), full screen in 4 frames")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Address layout
    palette_data_addr = 0x6800     # 128 bytes
    gargoyle_addr = 0x6880         # 8 bytes
    spider_addr = 0x6888           # 8 bytes
    init_routine_addr = 0x6890     # ~122 bytes
    palette_loader_addr = 0x6910   # 79 bytes
    hdma_colorizer_addr = 0x6960   # ~150 bytes (HDMA-based)
    shadow_main_addr = 0x6A00      # 52 bytes
    combined_addr = 0x6A40         # 16 bytes
    lookup_table_addr = 0x6B00     # 256 bytes (ALIGNED!)
    colorizer_addr = 0x6C00        # 90 bytes, MUST BE HERE

    # WRAM addresses
    attr_buffer_addr = 0xD000      # 256 bytes for one chunk

    # HRAM addresses
    init_done_flag = 0xC0          # 0xFFC0
    row_counter_addr = 0xC1        # 0xFFC1 - which chunk (0-3)

    lookup_table = create_tile_palette_lookup()
    onetime_init = create_onetime_init(init_done_flag)
    palette_loader = create_fast_palette_loader(palette_data_addr, gargoyle_addr, spider_addr,
                                                 init_routine_addr, init_done_flag)
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    hdma_colorizer = create_hdma_bg_colorizer(lookup_table_addr, attr_buffer_addr, row_counter_addr)
    combined = create_combined_with_hdma(palette_loader_addr, shadow_main_addr, hdma_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")
    print(f"One-time init: {len(onetime_init)} bytes at 0x{init_routine_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"HDMA colorizer: {len(hdma_colorizer)} bytes at 0x{hdma_colorizer_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"Attr buffer: 256 bytes at 0x{attr_buffer_addr:04X} (WRAM)")

    # Verify no overlaps
    hdma_end = hdma_colorizer_addr + len(hdma_colorizer)
    print(f"\nHDMA colorizer ends at 0x{hdma_end:04X}")
    if hdma_end > shadow_main_addr:
        print(f"WARNING: HDMA colorizer overlaps shadow_main!")
        return

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(gargoyle_addr, gargoyle)
    write_to_bank13(spider_addr, spider)
    write_to_bank13(lookup_table_addr, lookup_table)
    write_to_bank13(init_routine_addr, onetime_init)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(hdma_colorizer_addr, hdma_colorizer)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")


if __name__ == "__main__":
    main()
