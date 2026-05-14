#!/usr/bin/env python3
"""
v1.40: HDMA BG Colorization with Refined Tile Ranges

Based on detailed tile analysis:
- 0x00-0x0F: Floor base tiles (palette 0 - blue)
- 0x10-0x1F: Wall borders/edges (palette 2 - purple)
- 0x20-0x2F: Wall corners/decoration (palette 2)
- 0x30-0x3F: Wall structure (palette 2)
- 0x40-0x7F: Extended wall/special (palette 2)
- 0x80-0xBF: Hazards/spikes (palette 3 - green)
- 0xC0-0xDF: Items/pickups (palette 1 - GOLD!)
- 0xE0-0xFF: Wall edges/borders (palette 2)

Note: Items in 0xC0-0xDF range should appear gold.
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
    """
    Create 256-byte lookup table with refined tile ranges.

    Based on actual Level 1 tile usage:
    - Floor: 0x00-0x06 (basic checkerboard)
    - Wall borders: 0x13-0x1F
    - Wall corners: 0x20-0x29
    - Floor chains/deco: 0x2A-0x2F -> palette 0 (was incorrectly 2)
    - Wall tiles: 0x30-0x39
    - Floor deco: 0x3A-0x3F -> palette 0
    - Extended: 0x40-0x7F -> palette 2
    - Hazards: 0x80-0xBF -> palette 3
    - Items: 0xC0-0xDF -> palette 1 (GOLD)
    - Wall edges: 0xE0-0xFF -> palette 2
    """
    lookup = bytearray(256)
    for i in range(256):
        if i <= 0x0F:
            # Floor base tiles
            lookup[i] = 0
        elif i <= 0x12:
            # Transition tiles
            lookup[i] = 0
        elif i <= 0x1F:
            # Wall borders
            lookup[i] = 2
        elif i <= 0x29:
            # Wall corners/decoration
            lookup[i] = 2
        elif i <= 0x2F:
            # Floor chains/decorations (chains at bottom of screen)
            lookup[i] = 0  # Keep as floor, not wall!
        elif i <= 0x39:
            # Wall structure tiles
            lookup[i] = 2
        elif i <= 0x3F:
            # Floor decorative patterns
            lookup[i] = 0  # Keep as floor!
        elif i <= 0x7F:
            # Extended wall/structure
            lookup[i] = 2
        elif i <= 0xBF:
            # Hazards (spikes, etc)
            lookup[i] = 3
        elif i <= 0xDF:
            # Items - GOLD!
            lookup[i] = 1
        else:
            # Wall edges (0xE0-0xFF including 0xFE)
            lookup[i] = 2
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
    """HDMA BG colorizer with tilemap detection."""
    code = bytearray()

    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Check LCDC bit 3 for tilemap base
    code.extend([0xF0, 0x40])
    code.extend([0xE6, 0x08])
    code.extend([0x28, 0x04])
    code.extend([0x3E, 0x9C])
    code.extend([0x18, 0x02])
    code.extend([0x3E, 0x98])
    code.append(0x57)

    # Get row chunk
    code.extend([0xF0, row_counter_addr & 0xFF])
    code.extend([0xE6, 0x03])
    code.append(0x47)

    # Calculate offset
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)

    code.append(0x82)
    code.append(0x67)
    code.extend([0x2E, 0x00])

    code.append(0x7C)
    code.append(0x5F)

    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x4F])

    code.append(0xD5)
    code.extend([0x11, attr_buffer_addr & 0xFF, (attr_buffer_addr >> 8) & 0xFF])

    code.extend([0x0E, (lookup_table_addr >> 8) & 0xFF])

    code.extend([0x3E, 0x08])
    code.append(0xF5)

    outer_loop = len(code)
    code.extend([0x06, 0x20])

    inner_loop = len(code)
    code.append(0x7E)
    code.append(0x23)
    code.append(0xE5)
    code.append(0x6F)
    code.append(0x61)
    code.append(0x7E)
    code.append(0xE1)
    code.append(0x12)
    code.append(0x13)
    code.append(0x05)
    code.extend([0x20, (inner_loop - len(code) - 2) & 0xFF])

    code.append(0xF1)
    code.append(0x3D)
    code.extend([0x28, 0x03])
    code.append(0xF5)
    code.extend([0x18, (outer_loop - len(code) - 2) & 0xFF])

    code.append(0xD1)

    code.extend([0xF0, row_counter_addr & 0xFF])
    code.extend([0xE6, 0x03])
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x83)
    code.append(0x57)

    code.extend([0x3E, 0x01])
    code.extend([0xE0, 0x4F])

    code.extend([0x3E, (attr_buffer_addr >> 8) & 0xFF])
    code.extend([0xE0, 0x51])
    code.extend([0x3E, attr_buffer_addr & 0xFF])
    code.extend([0xE0, 0x52])
    code.append(0x7A)
    code.extend([0xE0, 0x53])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x54])

    code.extend([0x3E, 0x8F])
    code.extend([0xE0, 0x55])

    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x4F])

    code.extend([0xF0, row_counter_addr & 0xFF])
    code.append(0x3C)
    code.extend([0xE0, row_counter_addr & 0xFF])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_onetime_init(init_done_flag: int) -> bytes:
    """Hybrid palette initialization."""
    code = bytearray()

    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])

    for _ in range(8):
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    code.extend([0x06, 0x38])
    code.append(0xAF)
    bg_loop = len(code)
    code.extend([0xE0, 0x69])
    code.append(0x05)
    code.extend([0x20, (bg_loop - len(code) - 2) & 0xFF])

    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])

    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0xFF]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x7F]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x94]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x52]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x08]); code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x21]); code.extend([0xE0, 0x6B])

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
    """Fast palette loader."""
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
    """Combined function."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v140.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.40: HDMA with Refined Tile Ranges ===")
    print("  Floor deco (0x2A-0x3F) now palette 0 instead of 2")
    print("  Items (0xC0-0xDF) -> palette 1 (gold)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    init_routine_addr = 0x6890
    palette_loader_addr = 0x6910
    hdma_colorizer_addr = 0x6960
    shadow_main_addr = 0x6A10
    combined_addr = 0x6A50
    lookup_table_addr = 0x6B00
    colorizer_addr = 0x6C00

    attr_buffer_addr = 0xD000
    init_done_flag = 0xC0
    row_counter_addr = 0xC1

    lookup_table = create_tile_palette_lookup()
    onetime_init = create_onetime_init(init_done_flag)
    palette_loader = create_fast_palette_loader(palette_data_addr, gargoyle_addr, spider_addr,
                                                 init_routine_addr, init_done_flag)
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    hdma_colorizer = create_hdma_bg_colorizer(lookup_table_addr, attr_buffer_addr, row_counter_addr)
    combined = create_combined_with_hdma(palette_loader_addr, shadow_main_addr, hdma_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"HDMA colorizer: {len(hdma_colorizer)} bytes")

    hdma_end = hdma_colorizer_addr + len(hdma_colorizer)
    if hdma_end > shadow_main_addr:
        print(f"ERROR: Overlap!")
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
