#!/usr/bin/env python3
"""
v2.25: Fix Uninitialized HRAM Bug - Load Palettes Every Frame

CRITICAL FIX: Removed one-shot HRAM check that caused blank screen.
- v2.22/v2.25 checked uninitialized HRAM 0xFFE1, preventing palette load
- v2.25 matches v1.09: loads palettes EVERY frame (no check)

Other fixes from v2.25:
- Input handler: 8 delay reads (matches original)
- Input handler: Returns value in A register

PURPOSE: Add BG colorization without breaking the working OBJ colorization.

DESIGN:
- OBJ colorization: Unchanged from v2.19 (uses 0xFFBE for Sara, tile-based for enemies)
- BG colorization: One-shot approach that only runs once per level entry
  - Detects gameplay start via 0xFFC1 (0->non-zero transition)
  - Processes 2 rows per VBlank (safe timing budget)
  - Uses completion flag to stop after full screen is colorized
  - Only restarts when 0xFFC1 goes back to 0 (menu/transition)

KEY DIFFERENCE from v2.17/v2.18:
- v2.17/v2.18 did BG colorization EVERY frame
- v2.20 does BG colorization ONCE per level (18 VBlanks to complete)
- After completion, NO BG work is done until next level

HRAM Usage:
- 0xFFE0: BG row counter (0-17) - note: 0xFFD0 is used by game, causes corruption

Tile palette lookup (BG):
- 0x00-0x1F: Floor -> Palette 0 (blue)
- 0x20-0x7F: Walls -> Palette 2 (purple)
- 0x80-0xDF: Items -> Palette 1 (gold)
- 0xE0-0xFF: Borders -> Palette 2 (purple)
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
    """Load palettes from YAML file."""
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


def create_tile_based_colorizer() -> bytes:
    """
    OBJ colorizer - UNCHANGED from v2.19.
    Uses D register for Sara palette, E register for boss override.
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    code.extend([0x06, 0x28])  # LD B, 40

    labels['loop_start'] = len(code)

    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B
    code.extend([0xFE, 0x04])        # CP 4
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])        # JR C, sara_palette

    code.append(0x2B)                # DEC HL
    code.append(0x7E)                # LD A, [HL]
    code.append(0x23)                # INC HL
    code.append(0x4F)                # LD C, A

    code.extend([0xFE, 0x10])        # CP 0x10
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])        # JR C

    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])        # JR NZ

    code.append(0x79)                # LD A, C

    code.extend([0xFE, 0x50])        # CP 0x50
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])

    code.extend([0xFE, 0x60])        # CP 0x60
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])

    code.extend([0xFE, 0x70])        # CP 0x70
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])

    code.extend([0xFE, 0x80])        # CP 0x80
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])

    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['check_hornet'] = len(code)
    code.append(0x79)                # LD A, C
    code.extend([0xFE, 0x40])        # CP 0x40
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])        # JR NC, hornet_palette (if tile >= 0x40)
    code.extend([0xFE, 0x30])        # CP 0x30
    jumps_to_fix.append((len(code), 'crow_palette'))
    code.extend([0x30, 0x00])        # JR NC, crow_palette (if tile >= 0x30)
    code.extend([0x3E, 0x04])        # LD A, 4 (tiles 0x10-0x2F = misc)
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['crow_palette'] = len(code)
    code.extend([0x3E, 0x03])        # LD A, 3 (Crow palette)
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['sara_palette'] = len(code)
    code.append(0x7A)                # LD A, D
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['boss_palette'] = len(code)
    code.append(0x7B)                # LD A, E
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])        # LD A, 5
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])        # LD A, 6
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])

    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7

    labels['apply_palette'] = len(code)
    code.append(0x4F)                # LD C, A
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A

    code.extend([0x23, 0x23, 0x23, 0x23])
    code.append(0x05)                # DEC B
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])
    code.append(0xC9)                # RET

    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """OBJ colorizer main - UNCHANGED from v2.19."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    code.extend([0xF0, 0xBE])        # LDH A, [FFBE]
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x04])        # JR NZ, +4 (Dragon)
    code.extend([0x16, 0x02])        # LD D, 2 (Witch)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x16, 0x01])        # LD D, 1 (Dragon)

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

    code.extend([0x21, 0x03, 0xC0])  # LD HL, 0xC003
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0x21, 0x03, 0xC1])  # LD HL, 0xC103
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)
    return bytes(code)


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """
    Palette loader - EVERY FRAME version (like v1.09).
    Fixed: Removed one-shot check that relied on uninitialized HRAM 0xFFE1.
    """
    code = bytearray()

    # Load BG palettes (no check - load every frame like v1.09)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x0E, 0x40])
    code.extend([0x2A])
    code.extend([0xE0, 0x69])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x30])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x03])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    code.append(0xC9)
    return bytes(code)


def create_bg_colorizer_oneshot(lookup_table_addr: int) -> bytes:
    """
    One-shot BG colorizer - processes 1 row per VBlank.

    Uses HRAM 0xFFE0 for row counter (0xFFD0 was used by game).
    Completes all 18 rows in 18 VBlanks (~300ms).
    """
    code = bytearray()

    # Ensure VBK is 0 first
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

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

    # Read tile ID from bank 0
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A
    code.append(0x56)                      # LD D, [HL]

    # Look up palette
    code.append(0xE5)                      # PUSH HL
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])
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
    code.extend([0x0E, 0x02])              # LD C, 2

    row_loop_start = len(code)
    code.append(0xC5)                      # PUSH BC (row counter)

    # Process 32 tiles
    code.extend([0x06, 0x20])              # LD B, 32

    tile_loop_start = len(code)

    # Read tile ID from bank 0
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A
    code.append(0x56)                      # LD D, [HL]

    # Look up palette
    code.append(0xE5)                      # PUSH HL
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])
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

    code.append(0xC1)                      # POP BC (row counter)
    code.append(0x0D)                      # DEC C
    row_offset = row_loop_start - len(code) - 2
    code.extend([0x20, row_offset & 0xFF])

    # Restore saved registers
    code.append(0xD1)                      # POP DE
    code.append(0xC1)                      # POP BC

    # Update HRAM counter: add 2
    code.extend([0xF0, 0xE0])              # LDH A, [0xE0]
    code.extend([0xC6, 0x02])              # ADD A, 2
    code.extend([0xE0, 0xD0])              # LDH [0xD0], A

    # Reset VBK
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    code.append(0xC9)                      # RET

    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, obj_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function: load palettes, colorize OBJ, run DMA (BG DISABLED)."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, obj_main_addr & 0xFF, obj_main_addr >> 8])
    # BG colorizer DISABLED - was causing display issues
    # code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # CALL DMA
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook with input handler - matches original timing."""
    # Input handler matching original (0x0824-0x0851)
    input_handler = bytearray([
        # Read buttons (start/select/B/A)
        0x3E, 0x20,                                    # LD A, 0x20
        0xE0, 0x00,                                    # LDH [P1], A
        0xF0, 0x00,                                    # LDH A, [P1]
        0xF0, 0x00,                                    # LDH A, [P1] (delay)
        0x2F,                                          # CPL
        0xE6, 0x0F,                                    # AND 0x0F
        0xCB, 0x37,                                    # SWAP A
        0x47,                                          # LD B, A

        # Read d-pad (up/down/left/right) with 8 delay reads
        0x3E, 0x10,                                    # LD A, 0x10
        0xE0, 0x00,                                    # LDH [P1], A
        0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00,  # 4 delay reads
        0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0xF0, 0x00,  # 4 more delay reads
        0x2F,                                          # CPL
        0xE6, 0x0F,                                    # AND 0x0F
        0xB0,                                          # OR B (combine with buttons)
        0xE0, 0x93,                                    # LDH [0xFF93], A (store input)
        0x47,                                          # LD B, A (save for return)

        # Reset P1
        0x3E, 0x30,                                    # LD A, 0x30
        0xE0, 0x00,                                    # LDH [P1], A
        0x78,                                          # LD A, B (return input in A)
    ])
    # MBC1 requires both 0x2000 (low 5 bits) and 0x4000 (high 2 bits) for bank selection
    hook_code = bytearray([
        0x3E, 0x0D, 0xEA, 0x00, 0x20,  # LD A, 13; LD [0x2000], A (low 5 bits)
        0xAF, 0xEA, 0x00, 0x40,        # XOR A; LD [0x4000], A (clear high 2 bits)
        0xCD, combined_func_addr & 0xFF, combined_func_addr >> 8,
        0x3E, 0x01, 0xEA, 0x00, 0x20,  # LD A, 1; LD [0x2000], A (back to bank 1)
        0xC9,
    ])
    return bytes(input_handler + hook_code)


def main():
    project_root = Path(__file__).parent.parent
    input_rom = project_root / "rom/Penta Dragon (J).gb"
    output_rom = project_root / "rom/working/penta_dragon_dx_v225.gb"
    fixed_rom = project_root / "rom/working/penta_dragon_dx_FIXED.gb"
    palette_path = project_root / "palettes/penta_palettes_v097.yaml"

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)
    lookup_table = create_tile_palette_lookup()

    print("\n=== v2.25: Fix Blank Screen - Remove HRAM Check ===")
    print("  CRITICAL FIX: Palette loader now loads EVERY frame (like v1.09)")
    print("    - Removed check for uninitialized HRAM 0xFFE1")
    print("    - This was causing blank screen in v2.22/v2.25")
    print("  Input: 8 delay reads, returns in A register")
    print("  OBJ: Tile-based | BG: One-shot (disabled for now)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    lookup_table_addr = 0x6900
    colorizer_addr = 0x6A00
    shadow_main_addr = 0x6A80
    palette_loader_addr = 0x6AE0
    bg_colorizer_addr = 0x6B40
    combined_addr = 0x6C00

    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_colorizer = create_bg_colorizer_oneshot(lookup_table_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Lookup table: 256 bytes at 0x{lookup_table_addr:04X}")
    print(f"OBJ colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"OBJ main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"VBlank hook: {len(vblank_hook)} bytes at 0x0824")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def bank_offset(addr):
        return bank13_offset + (addr - 0x4000)

    # Write data
    rom[bank_offset(palette_data_addr):bank_offset(palette_data_addr) + len(bg_data)] = bg_data
    rom[bank_offset(palette_data_addr) + 64:bank_offset(palette_data_addr) + 64 + len(obj_data)] = obj_data
    rom[bank_offset(gargoyle_addr):bank_offset(gargoyle_addr) + len(gargoyle)] = gargoyle
    rom[bank_offset(spider_addr):bank_offset(spider_addr) + len(spider)] = spider
    rom[bank_offset(lookup_table_addr):bank_offset(lookup_table_addr) + len(lookup_table)] = lookup_table

    # Write code
    rom[bank_offset(colorizer_addr):bank_offset(colorizer_addr) + len(colorizer)] = colorizer
    rom[bank_offset(shadow_main_addr):bank_offset(shadow_main_addr) + len(shadow_main)] = shadow_main
    rom[bank_offset(palette_loader_addr):bank_offset(palette_loader_addr) + len(palette_loader)] = palette_loader
    rom[bank_offset(bg_colorizer_addr):bank_offset(bg_colorizer_addr) + len(bg_colorizer)] = bg_colorizer
    rom[bank_offset(combined_addr):bank_offset(combined_addr) + len(combined)] = combined

    # Patch entry points
    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    rom[0x143] = 0x80  # CGB compatible mode
    print("Set CGB flag at 0x143 to 0x80 (CGB compatible)")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v2.25 Build Complete ===")


if __name__ == "__main__":
    main()
