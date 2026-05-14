#!/usr/bin/env python3
"""
Diagnostic: Copy palette data to WRAM first, then load from WRAM.
Tests if the issue is with ROM reads vs WRAM reads.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes]:
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

    return bytes(bg_data), bytes(obj_data)


def create_wram_palette_loader(rom_data_addr: int) -> bytes:
    """
    1. Copy 128 bytes from ROM (0x6800) to WRAM (0xD000)
    2. Load BG palettes from WRAM 0xD000
    3. Load OBJ palettes from WRAM 0xD040
    """
    code = bytearray()

    # Step 1: Copy 128 bytes from ROM to WRAM
    code.extend([0x21, rom_data_addr & 0xFF, (rom_data_addr >> 8) & 0xFF])  # LD HL, rom_addr (0x6800)
    code.extend([0x11, 0x00, 0xD0])  # LD DE, 0xD000 (WRAM)
    code.extend([0x01, 0x80, 0x00])  # LD BC, 128

    # Copy loop
    copy_start = len(code)
    code.append(0x2A)                # LD A, [HL+]
    code.append(0x12)                # LD [DE], A
    code.append(0x13)                # INC DE
    code.append(0x0B)                # DEC BC
    code.append(0x78)                # LD A, B
    code.append(0xB1)                # OR C
    copy_offset = copy_start - len(code) - 2
    code.extend([0x20, copy_offset & 0xFF])

    # Step 2: Load BG palettes from WRAM 0xD000
    code.extend([0x21, 0x00, 0xD0])  # LD HL, 0xD000
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x68])        # LDH [BCPS], A
    code.extend([0x0E, 0x40])        # LD C, 64
    bg_loop = len(code)
    code.append(0x2A)                # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [BCPD], A
    code.append(0x0D)                # DEC C
    bg_offset = bg_loop - len(code) - 2
    code.extend([0x20, bg_offset & 0xFF])

    # Step 3: Load OBJ palettes from WRAM 0xD040
    # HL is already at 0xD040 after BG loop
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x6A])        # LDH [OCPS], A
    code.extend([0x0E, 0x40])        # LD C, 64
    obj_loop = len(code)
    code.append(0x2A)                # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [OCPD], A
    code.append(0x0D)                # DEC C
    obj_offset = obj_loop - len(code) - 2
    code.extend([0x20, obj_offset & 0xFF])

    code.append(0xC9)                # RET
    return bytes(code)


def create_force_palette4_colorizer() -> bytes:
    code = bytearray()
    code.extend([0x06, 0x28])
    loop_start = len(code)
    code.append(0x7E)
    code.extend([0xE6, 0xF8])
    code.extend([0xF6, 0x04])
    code.append(0x77)
    code.extend([0x23, 0x23, 0x23, 0x23])
    code.append(0x05)
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


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int) -> bytes:
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook(combined_func_addr: int) -> bytes:
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
    output_rom = Path("rom/working/penta_dragon_dx_WRAM.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print("=== DIAGNOSTIC: WRAM-based palette loading ===")
    print("1. Copy ROM palette data to WRAM")
    print("2. Load palettes from WRAM (not ROM)")
    print("If sprites turn yellow -> ROM read issue")
    print("If sprites stay blue -> Loop/timing issue")
    print()

    bg_data, obj_data = load_palettes_from_yaml(palette_path)

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    palette_data_addr = 0x6800  # ROM data in bank 13
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6920
    palette_loader_addr = 0x6950
    combined_addr = 0x69D0

    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_wram_palette_loader(palette_data_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    print(f"\nWrote: {output_rom}")


if __name__ == "__main__":
    main()
