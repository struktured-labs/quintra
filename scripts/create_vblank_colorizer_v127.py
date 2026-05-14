#!/usr/bin/env python3
"""
v1.27: HDMA BG Colorization with Correct Tile Mappings

Fixed tile→palette mappings based on actual tilemap analysis:
- Floor tiles (0x00-0x0F): palette 0 (dungeon floor)
- Wall/edge tiles (0x10-0x3F): palette 2 (purple walls)
- Decoration tiles (0x40-0x7F): palette 0 (same as floor - doors etc)
- Items/special (0x80-0xDF): palette 1 (gold) if any
- Border (0xFE, 0xFF): palette 0

Tilemap analysis showed:
- 0x01, 0x02, 0x03, 0x04, 0x06 = floor checkerboard
- 0x17, 0x24-0x27, 0x30, 0x33, 0x35, 0x36 = wall/edge
- 0x40-0x5B = door/window decorations (on floor)
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
    Create 256-byte lookup table: tile ID -> BG palette.

    Based on actual tilemap analysis from level 1:
    - 0x00-0x0F: Floor/empty -> palette 0
    - 0x10-0x3F: Wall/edge tiles -> palette 2
    - 0x40-0x7F: Decorations (doors, windows) -> palette 0 (blend with floor)
    - 0x80-0xBF: Could be items/special -> palette 1
    - 0xC0-0xFD: Could be hazards -> palette 3
    - 0xFE-0xFF: Border/special -> palette 0
    """
    lookup = bytearray(256)

    # Floor tiles (palette 0) - dungeon main colors
    for t in range(0x00, 0x10):
        lookup[t] = 0

    # Wall/edge tiles (palette 2) - purple/blue walls
    for t in range(0x10, 0x40):
        lookup[t] = 2

    # Decoration tiles (palette 0) - same as floor for doors, windows
    for t in range(0x40, 0x80):
        lookup[t] = 0

    # Items/collectibles (palette 1) - gold/yellow
    for t in range(0x80, 0xC0):
        lookup[t] = 1

    # Hazards/spikes (palette 3) - green/danger
    for t in range(0xC0, 0xFE):
        lookup[t] = 3

    # Border/special (palette 0)
    lookup[0xFE] = 0
    lookup[0xFF] = 0

    return bytes(lookup)


def create_tile_based_colorizer() -> bytes:
    """OBJ colorizer (same as v1.09)."""
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


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes."""
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


def create_hdma_bg_colorizer(lookup_table_addr: int) -> bytes:
    """
    HDMA-based BG colorizer.
    Processes 256 tiles per frame in 4 batches (full tilemap every 4 frames).
    """
    code = bytearray()
    lookup_high = (lookup_table_addr >> 8) & 0xFF

    # Save all registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Get batch counter (0-3)
    code.extend([0xF0, 0xBC])              # LDH A, [0xFFBC]
    code.extend([0xE6, 0x03])              # AND 0x03

    # Calculate VRAM source high byte: 0x98 + batch
    code.extend([0xC6, 0x98])              # ADD A, 0x98
    code.extend([0xE0, 0xBE])              # LDH [0xFFBE], A (save for HDMA dest)
    code.append(0x67)                       # LD H, A
    code.extend([0x2E, 0x00])              # LD L, 0

    # Switch to VRAM bank 0 for reading tile IDs
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # DE = WRAM buffer at 0xD000
    code.extend([0x11, 0x00, 0xD0])        # LD DE, 0xD000

    # BC = 256 (0x0100) - loop counter
    code.extend([0x01, 0x00, 0x01])        # LD BC, 0x0100

    # Build loop
    loop_start = len(code)
    code.append(0x2A)                       # LD A, [HL+]
    code.append(0xE5)                       # PUSH HL
    code.append(0x6F)                       # LD L, A
    code.extend([0x26, lookup_high])       # LD H, lookup_high
    code.append(0x7E)                       # LD A, [HL]
    code.append(0xE1)                       # POP HL
    code.append(0x12)                       # LD [DE], A
    code.append(0x13)                       # INC DE
    code.append(0x0B)                       # DEC BC
    code.append(0x78)                       # LD A, B
    code.append(0xB1)                       # OR C
    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])

    # Configure HDMA
    code.extend([0x3E, 0xD0])              # LD A, 0xD0
    code.extend([0xE0, 0x51])              # LDH [HDMA1], A
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x52])              # LDH [HDMA2], A
    code.extend([0xF0, 0xBE])              # LDH A, [0xFFBE]
    code.extend([0xE0, 0x53])              # LDH [HDMA3], A
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x54])              # LDH [HDMA4], A

    # Switch to VRAM bank 1
    code.extend([0x3E, 0x01])              # LD A, 1
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Start HDMA
    code.extend([0x3E, 0x8F])              # LD A, 0x8F
    code.extend([0xE0, 0x55])              # LDH [HDMA5], A

    # Switch back to VRAM bank 0
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Increment batch counter
    code.extend([0xF0, 0xBC])              # LDH A, [0xFFBC]
    code.append(0x3C)                       # INC A
    code.extend([0xE6, 0x03])              # AND 0x03
    code.extend([0xE0, 0xBC])              # LDH [0xFFBC], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_combined_with_hdma(palette_loader_addr: int, shadow_main_addr: int, hdma_bg_addr: int) -> bytes:
    """Combined: load palettes, colorize OBJ shadows, HDMA BG colorize, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, hdma_bg_addr & 0xFF, hdma_bg_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook at 0x0824."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v127.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.27: HDMA BG with Corrected Tile Mappings ===")
    print("  Floor (0x00-0x0F, 0x40-0x7F): palette 0")
    print("  Walls (0x10-0x3F): palette 2 (purple)")
    print("  Items (0x80-0xBF): palette 1 (gold)")
    print("  Hazards (0xC0-0xFD): palette 3 (green)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    obj_colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    hdma_bg_addr = 0x6A40
    combined_addr = 0x6AC0
    lookup_table_addr = 0x6B00

    # Generate code
    tile_lookup = create_tile_palette_lookup()
    obj_colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(obj_colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    hdma_bg = create_hdma_bg_colorizer(lookup_table_addr)
    combined = create_combined_with_hdma(palette_loader_addr, shadow_main_addr, hdma_bg_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Tile lookup table: {len(tile_lookup)} bytes at 0x{lookup_table_addr:04X}")
    print(f"OBJ colorizer: {len(obj_colorizer)} bytes at 0x{obj_colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"HDMA BG colorizer: {len(hdma_bg)} bytes at 0x{hdma_bg_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(gargoyle_addr, gargoyle)
    write_to_bank13(spider_addr, spider)
    write_to_bank13(obj_colorizer_addr, obj_colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(hdma_bg_addr, hdma_bg)
    write_to_bank13(combined_addr, combined)
    write_to_bank13(lookup_table_addr, tile_lookup)

    # NOP out original DMA
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])

    # VBlank hook
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.27 Build Complete ===")


if __name__ == "__main__":
    main()
