#!/usr/bin/env python3
"""
Test: Does looping 64 bytes work after hardcoded init?
OVERWRITE worked with 8 bytes. Test if 64 bytes also works.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_test_loader(data_addr: int) -> bytes:
    """
    1. Hardcoded BLUE to all OBJ palettes
    2. Loop-based overwrite of ALL 64 bytes with data from ROM
    """
    code = bytearray()

    # BG palettes - just zeros
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    for _ in range(64):
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    # OBJ palettes - hardcoded BLUE first
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    for _ in range(8):  # 8 palettes
        code.extend([0x3E, 0x00])  # trans lo
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])  # trans hi
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0xE0])  # blue lo
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x7F])  # blue hi
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0xC0])  # dark blue lo
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x3C])  # dark blue hi
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])  # black lo
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])  # black hi
        code.extend([0xE0, 0x6B])

    # Now try to overwrite ALL 64 bytes with loop
    code.extend([0x21, data_addr & 0xFF, (data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])  # OCPS = 0x80 (start from palette 0)
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x40])  # LD C, 64
    loop_start = len(code)
    code.append(0x7E)          # LD A, [HL]
    code.extend([0xE0, 0x6B])  # LDH [OCPD], A
    code.append(0x23)          # INC HL
    code.append(0x0D)          # DEC C
    code.extend([0x20, (loop_start - len(code) - 2) & 0xFF])

    code.append(0xC9)
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


def create_combined(palette_loader: int, colorizer_main: int) -> bytes:
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
    output_rom = Path("rom/working/penta_dragon_dx_LOOP64.gb")

    print("=== Test: Hardcoded BLUE -> Loop 64 bytes YELLOW ===")

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Yellow palette data for all 8 palettes (64 bytes)
    # Palette 4 = yellow, others = gray
    yellow_data = bytearray()
    for pal in range(8):
        if pal == 4:
            yellow_data.extend([0x00, 0x00])  # trans
            yellow_data.extend([0xFF, 0x03])  # yellow
            yellow_data.extend([0xDF, 0x00])  # orange
            yellow_data.extend([0x00, 0x00])  # black
        else:
            yellow_data.extend([0x00, 0x00])  # trans
            yellow_data.extend([0xFF, 0x7F])  # white
            yellow_data.extend([0x94, 0x52])  # gray
            yellow_data.extend([0x08, 0x21])  # dark

    data_addr = 0x0200
    rom[data_addr:data_addr + len(yellow_data)] = yellow_data

    palette_loader_addr = 0x6800
    colorizer_addr = 0x6E00
    colorizer_main_addr = 0x6E20
    combined_addr = 0x6E50

    palette_loader = create_test_loader(data_addr)
    colorizer = create_force_palette4_colorizer()
    colorizer_main = create_shadow_colorizer_main(colorizer_addr)
    combined = create_combined(palette_loader_addr, colorizer_main_addr)
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
    print()
    print("Expected: YELLOW sprites (loop overwrote BLUE init)")
    print("If BLUE: loop of 64 bytes doesn't work")


if __name__ == "__main__":
    main()
