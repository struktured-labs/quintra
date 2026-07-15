#!/usr/bin/env python3
"""
Copy the EXACT working approach from test_hardcoded_palette.py
but simplified - start from OCPS=0x80 and write ALL 64 bytes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_working_palette_loader() -> bytes:
    """
    Write ALL OBJ palettes from start (OCPS=0x80).
    Palette 4 = RED, others = gray.
    """
    code = bytearray()

    # BG palettes - simple grayscale for all
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x68])        # LDH [BCPS], A

    for _ in range(8):  # 8 BG palettes
        # White
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x69])
        # Gray
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x69])
        # Dark
        code.extend([0x3E, 0x4A])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x29])
        code.extend([0xE0, 0x69])
        # Black
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    # OBJ palettes - start from 0x80
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x6A])        # LDH [OCPS], A

    # Palettes 0-3: Gray
    for _ in range(4):
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])

    # Palette 4: RED
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x1F])  # RED
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x0F])  # Dark red
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])

    # Palettes 5-7: Gray
    for _ in range(3):
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])

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
    output_rom = Path("rom/working/penta_dragon_dx_FULLHARD.gb")

    print("=== Full hardcoded palette loader (like working HARDCODED test) ===")

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Need more space for full hardcoded version
    palette_loader_addr = 0x6800
    colorizer_addr = 0x6B00  # After palette loader
    shadow_main_addr = 0x6B20
    combined_addr = 0x6B50

    palette_loader = create_working_palette_loader()
    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    print(f"\nWrote: {output_rom}")


if __name__ == "__main__":
    main()
