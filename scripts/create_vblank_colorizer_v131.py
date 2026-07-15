#!/usr/bin/env python3
"""
v1.31: Uses EXACT approach from working OVERWRITE test.

The OVERWRITE test worked by:
1. Hardcoded BG palettes (64 bytes with actual grayscale values)
2. Hardcoded OBJ palettes (64 bytes with BLUE values)
3. Loop overwrite of palette 4 with YELLOW

This version does:
1. Hardcoded BG + OBJ init (using grayscale, not zeros)
2. Loop-based loading of actual palettes from YAML
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes]:
    """Load BG and OBJ palettes from YAML file."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors: list[str]) -> bytes:
        result = bytearray()
        for c in colors:
            val = int(c, 16) & 0x7FFF
            result.extend([val & 0xFF, (val >> 8) & 0xFF])
        return bytes(result)

    # BG palettes
    bg_keys = ['Dungeon', 'BG1', 'BG2', 'BG3', 'BG4', 'BG5', 'BG6', 'BG7']
    bg_data = bytearray()
    for key in bg_keys:
        if key in data.get('bg_palettes', {}):
            bg_data.extend(pal_to_bytes(data['bg_palettes'][key]['colors']))
        else:
            bg_data.extend(pal_to_bytes(["7FFF", "5294", "2108", "0000"]))

    # OBJ palettes
    obj_keys = ['Effects', 'SaraDragon', 'SaraWitch', 'Crow',
                'Hornets', 'OrcGround', 'Humanoid', 'Catfish']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

    return bytes(bg_data), bytes(obj_data)


def create_init_and_load_palettes(bg_data_addr: int, obj_data_addr: int) -> bytes:
    """
    EXACT approach from working OVERWRITE test:
    1. Hardcoded grayscale init for BG and OBJ
    2. Loop-based loading of actual values
    """
    code = bytearray()

    # ===== PHASE 1: Hardcoded grayscale initialization =====
    # BG palettes (8 palettes * 4 colors * 2 bytes = 64 writes)
    code.extend([0x3E, 0x80])  # LD A, 0x80 (BCPS auto-increment)
    code.extend([0xE0, 0x68])  # LDH [BCPS], A

    for _ in range(8):  # 8 palettes
        # White: 0x7FFF
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x69])
        # Light gray: 0x5294
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x69])
        # Dark gray: 0x2108
        code.extend([0x3E, 0x08])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x21])
        code.extend([0xE0, 0x69])
        # Black: 0x0000
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    # OBJ palettes (8 palettes * 4 colors * 2 bytes = 64 writes)
    code.extend([0x3E, 0x80])  # LD A, 0x80 (OCPS auto-increment)
    code.extend([0xE0, 0x6A])  # LDH [OCPS], A

    for _ in range(8):  # 8 palettes
        # Transparent: 0x0000
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        # White: 0x7FFF
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x6B])
        # Gray: 0x5294
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x6B])
        # Dark: 0x2108
        code.extend([0x3E, 0x08])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x21])
        code.extend([0xE0, 0x6B])

    # ===== PHASE 2: Loop-based actual palette loading =====
    # Load BG palettes from ROM
    code.extend([0x21, bg_data_addr & 0xFF, (bg_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x0E, 0x40])  # LD C, 64
    bg_loop = len(code)
    code.append(0x7E)          # LD A, [HL]
    code.extend([0xE0, 0x69])  # LDH [BCPD], A
    code.append(0x23)          # INC HL
    code.append(0x0D)          # DEC C
    code.extend([0x20, (bg_loop - len(code) - 2) & 0xFF])

    # Load OBJ palettes from ROM
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x40])  # LD C, 64
    obj_loop = len(code)
    code.append(0x7E)          # LD A, [HL]
    code.extend([0xE0, 0x6B])  # LDH [OCPD], A
    code.append(0x23)          # INC HL
    code.append(0x0D)          # DEC C
    code.extend([0x20, (obj_loop - len(code) - 2) & 0xFF])

    code.append(0xC9)
    return bytes(code)


def create_force_palette4_colorizer() -> bytes:
    """Simple colorizer that forces all sprites to palette 4."""
    code = bytearray()
    code.extend([0x06, 0x28])  # LD B, 40
    loop_start = len(code)
    code.append(0x7E)          # LD A, [HL]
    code.extend([0xE6, 0xF8])  # AND 0xF8
    code.extend([0xF6, 0x04])  # OR 0x04
    code.append(0x77)          # LD [HL], A
    code.extend([0x23, 0x23, 0x23, 0x23])  # HL += 4
    code.append(0x05)          # DEC B
    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])
    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)
    return bytes(code)


def create_combined_function(palette_loader: int, colorizer_main: int) -> bytes:
    code = bytearray()
    code.extend([0xCD, palette_loader & 0xFF, palette_loader >> 8])
    code.extend([0xCD, colorizer_main & 0xFF, colorizer_main >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook(combined_addr: int) -> bytes:
    input_code = bytearray([
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
    ])
    hook_code = bytearray([
        0x3E, 0x0D,
        0xEA, 0x00, 0x20,
        0xCD, combined_addr & 0xFF, combined_addr >> 8,
        0x3E, 0x01,
        0xEA, 0x00, 0x20,
        0xC9,
    ])
    return bytes(input_code + hook_code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_v131.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print("=== Building v1.31: Grayscale init + loop loading ===")

    bg_data, obj_data = load_palettes_from_yaml(palette_path)

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Palette data in bank 0
    bg_data_addr = 0x0200
    obj_data_addr = 0x0240
    rom[bg_data_addr:bg_data_addr + len(bg_data)] = bg_data
    rom[obj_data_addr:obj_data_addr + len(obj_data)] = obj_data

    # Code in bank 13
    palette_loader_addr = 0x6800
    colorizer_addr = 0x6E00  # After large palette loader
    colorizer_main_addr = 0x6E20
    combined_addr = 0x6E50

    palette_loader = create_init_and_load_palettes(bg_data_addr, obj_data_addr)
    colorizer = create_force_palette4_colorizer()
    colorizer_main = create_shadow_colorizer_main(colorizer_addr)
    combined = create_combined_function(palette_loader_addr, colorizer_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Palette loader: {len(palette_loader)} bytes")

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(colorizer_main_addr, colorizer_main)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    print(f"Wrote: {output_rom}")


if __name__ == "__main__":
    main()
