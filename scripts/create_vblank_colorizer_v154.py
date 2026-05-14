#!/usr/bin/env python3
"""
v1.54: BG Tile Colorization via VBlank Row Updates

Building on v1.53's stable foundation:
- RST 08 hook for LCD-off VRAM bank 1 init (clears to palette 0)
- Sprite colorization via VBlank hook (unchanged from v1.09)

NEW: Gradual BG attribute updates during VBlank
- Each VBlank, update one row of tilemap attributes (32 tiles)
- Uses HRAM 0xFFC0 as row counter (0-31)
- Reads tile IDs from VRAM bank 0, writes attributes to bank 1
- Completes full tilemap in 32 frames (~0.5 seconds)
- After init, continues cycling to catch scroll updates

This avoids the timing issues of v1.50-52 by:
- Using VBlank (not HBlank or arbitrary times)
- Only doing 32 tiles per frame (not 1024)
- Building on proven v1.53 foundation
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


def create_bg_tile_lookup_table() -> bytes:
    """
    Create 256-byte lookup table: tile ID -> BG palette number.
    """
    table = bytearray(256)

    for i in range(256):
        if i < 0x10:
            table[i] = 0x00  # Floor - palette 0 (blue)
        elif i < 0x30:
            table[i] = 0x00  # Decorations - palette 0
        elif i < 0x4C:
            table[i] = 0x02  # Structure/walls - palette 2 (purple)
        elif i < 0x50:
            table[i] = 0x05  # Hazards - palette 5 (red)
        elif i < 0xA0:
            table[i] = 0x02  # Extended structure - palette 2
        elif i < 0xE0:
            table[i] = 0x01  # Items - palette 1 (gold)
        else:
            table[i] = 0x02  # Borders - palette 2

    return bytes(table)


def create_rst08_handler() -> bytes:
    """RST 08 handler at 0x0008 (exactly 8 bytes)."""
    code = bytearray()
    code.extend([0x3E, 0x04])           # LD A, 4
    code.extend([0xEA, 0x00, 0x20])     # LD [0x2000], A
    code.extend([0xC3, 0x00, 0x70])     # JP 0x7000
    assert len(code) == 8
    return bytes(code)


def create_vram_init_wrapper() -> bytes:
    """VRAM init wrapper at 0x7000 in bank 4."""
    code = bytearray()

    # Original code from 0x4003-0x400B
    code.extend([0x21, 0x00, 0x98])     # LD HL, 0x9800
    code.extend([0x01, 0x00, 0x10])     # LD BC, 0x1000
    code.extend([0xCD, 0xA8, 0x09])     # CALL 0x09A8

    # Initialize VRAM bank 1 to palette 0
    code.extend([0xC5, 0xD5, 0xE5])     # PUSH BC, DE, HL

    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    code.extend([0x21, 0x00, 0x98])     # LD HL, 0x9800
    code.extend([0x01, 0x00, 0x04])     # LD BC, 0x0400
    code.extend([0x3E, 0x00])           # LD A, 0

    loop_start = len(code)
    code.append(0x77)                   # LD [HL], A
    code.append(0x23)                   # INC HL
    code.append(0x0B)                   # DEC BC
    code.append(0x78)                   # LD A, B
    code.append(0xB1)                   # OR C
    code.extend([0x3E, 0x00])           # LD A, 0
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])  # JR NZ, loop

    code.append(0xAF)                   # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Initialize row counter at 0xFFC0 to 0
    code.extend([0xAF])                 # XOR A
    code.extend([0xE0, 0xC0])           # LDH [0xFFC0], A

    code.extend([0xE1, 0xD1, 0xC1])     # POP HL, DE, BC

    # Switch back to bank 1 and continue
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xEA, 0x00, 0x20])     # LD [0x2000], A
    code.extend([0xC3, 0x0C, 0x40])     # JP 0x400C

    return bytes(code)


def create_bg_row_colorizer(lookup_table_addr: int) -> bytes:
    """
    BG row colorizer - updates one row of tilemap attributes per call.

    Uses HRAM 0xFFC0 as row counter (0-31).
    Reads tile IDs from VRAM bank 0, looks up palette, writes to bank 1.

    Called during VBlank after sprite colorization.
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Get current row from 0xFFC0
    code.extend([0xF0, 0xC0])           # LDH A, [0xFFC0]
    code.append(0x47)                   # LD B, A (save row number)

    # Calculate tilemap row address: 0x9800 + row * 32
    # row * 32 = row << 5
    code.append(0x87)                   # ADD A, A (x2)
    code.append(0x87)                   # ADD A, A (x4)
    code.append(0x87)                   # ADD A, A (x8)
    code.append(0x87)                   # ADD A, A (x16)
    code.append(0x87)                   # ADD A, A (x32)
    code.append(0x6F)                   # LD L, A
    code.extend([0x26, 0x98])           # LD H, 0x98
    # If row >= 8, we need to add to H
    code.append(0x78)                   # LD A, B (restore row)
    code.extend([0xE6, 0x18])           # AND 0x18 (rows 8-31 overflow L)
    code.append(0x0F)                   # RRCA
    code.append(0x0F)                   # RRCA
    code.append(0x0F)                   # RRCA
    code.append(0x84)                   # ADD A, H
    code.append(0x67)                   # LD H, A

    # Now HL points to start of row in VRAM
    # DE will be used for lookup table
    code.extend([0x11, lookup_table_addr & 0xFF, (lookup_table_addr >> 8) & 0xFF])  # LD DE, lookup_table

    # Process 32 tiles in this row
    code.extend([0x0E, 0x20])           # LD C, 32

    # Read tile from VRAM bank 0, lookup palette, write to bank 1
    row_loop = len(code)

    # Ensure we're in VRAM bank 0 for reading
    code.append(0xAF)                   # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Read tile ID
    code.append(0x7E)                   # LD A, [HL]

    # Lookup palette: table[tile_id]
    code.append(0xE5)                   # PUSH HL
    code.append(0x6F)                   # LD L, A (tile ID)
    code.append(0x62)                   # LD H, D (lookup table high byte)
    code.append(0x7E)                   # LD A, [HL] (palette number)
    code.append(0x47)                   # LD B, A (save palette)
    code.append(0xE1)                   # POP HL

    # Switch to VRAM bank 1
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Write attribute (palette number)
    code.append(0x70)                   # LD [HL], B

    # Next tile
    code.append(0x23)                   # INC HL
    code.append(0x0D)                   # DEC C
    offset = row_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])  # JR NZ, row_loop

    # Switch back to VRAM bank 0
    code.append(0xAF)                   # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Increment row counter (wrap at 32)
    code.extend([0xF0, 0xC0])           # LDH A, [0xFFC0]
    code.append(0x3C)                   # INC A
    code.extend([0xE6, 0x1F])           # AND 0x1F (wrap at 32)
    code.extend([0xE0, 0xC0])           # LDH [0xFFC0], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                   # RET

    return bytes(code)


def create_tile_based_colorizer() -> bytes:
    """Tile-based sprite colorizer (same as v1.09)."""
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    code.extend([0x06, 0x28])  # LD B, 40
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


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes with dynamic boss palette swapping."""
    code = bytearray()

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


def create_combined_with_dma_and_bg(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function: load palettes, colorize shadows, colorize BG row, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])  # NEW: BG row colorizer
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
    output_rom = Path("rom/working/penta_dragon_dx_v154.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.54: BG Tile Colorization via VBlank Row Updates ===")
    print("  LCD-off VRAM bank 1 init (from v1.53)")
    print("  Sprite colorization (from v1.09)")
    print("  NEW: BG row colorizer - updates 32 tiles per VBlank")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # === RST 08 Handler ===
    rst08_handler = create_rst08_handler()
    print(f"RST 08 handler: {len(rst08_handler)} bytes at 0x0008")
    rom[0x0008:0x0008 + len(rst08_handler)] = rst08_handler

    # === Patch 0x4003 to RST 08 ===
    print(f"Original at 0x4003: {rom[0x4003:0x400C].hex()}")
    rom[0x4003] = 0xCF
    for i in range(0x4004, 0x400C):
        rom[i] = 0x00
    print(f"Patched 0x4003: CF (RST 08) + NOPs")

    # === VRAM Init Wrapper in Bank 4 ===
    vram_init_wrapper = create_vram_init_wrapper()
    bank4_offset = 4 * 0x4000
    wrapper_rom_offset = bank4_offset + (0x7000 - 0x4000)
    print(f"VRAM init wrapper: {len(vram_init_wrapper)} bytes at ROM 0x{wrapper_rom_offset:05X}")
    rom[wrapper_rom_offset:wrapper_rom_offset + len(vram_init_wrapper)] = vram_init_wrapper

    # === BG Tile Lookup Table in Bank 4 at 0x7100 ===
    lookup_table = create_bg_tile_lookup_table()
    lookup_table_addr = 0x7100  # CPU address when bank 4 loaded
    lookup_rom_offset = bank4_offset + (0x7100 - 0x4000)
    print(f"BG tile lookup table: {len(lookup_table)} bytes at ROM 0x{lookup_rom_offset:05X}")
    rom[lookup_rom_offset:lookup_rom_offset + len(lookup_table)] = lookup_table

    # === Bank 13 Layout ===
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    bg_colorizer_addr = 0x6A40  # NEW: BG row colorizer
    combined_addr = 0x6AC0      # Moved to accommodate BG colorizer

    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)

    # BG row colorizer needs lookup table address in bank 13's perspective
    # But wait - lookup table is in bank 4, and BG colorizer runs when bank 13 is active
    # We need to put lookup table in bank 13 OR switch banks in the BG colorizer

    # Let's put lookup table in bank 13 instead
    lookup_table_addr_bank13 = 0x6B00  # In bank 13
    bg_colorizer = create_bg_row_colorizer(lookup_table_addr_bank13)

    combined = create_combined_with_dma_and_bg(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG row colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"BG lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr_bank13:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    rom[bank13_offset + (colorizer_addr - 0x4000):bank13_offset + (colorizer_addr - 0x4000) + len(colorizer)] = colorizer
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (bg_colorizer_addr - 0x4000):bank13_offset + (bg_colorizer_addr - 0x4000) + len(bg_colorizer)] = bg_colorizer
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined
    rom[bank13_offset + (lookup_table_addr_bank13 - 0x4000):bank13_offset + (lookup_table_addr_bank13 - 0x4000) + len(lookup_table)] = lookup_table

    # NOP out DMA at 0x06D5
    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    # Write VBlank hook
    print(f"\nVBlank hook: {len(vblank_hook)} bytes")
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.54 Build Complete ===")
    print("\nBG colorization updates 32 tiles per VBlank frame.")
    print("Full tilemap colored in ~0.5 seconds, then cycles for scroll updates.")


if __name__ == "__main__":
    main()
