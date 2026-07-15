#!/usr/bin/env python3
"""
MINIMAL test: Load ONLY palette 4 with RED using a tiny loop.
Data: 00 00 1F 00 0F 00 00 00 (trans, red, dark red, trans)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_minimal_palette_loader() -> bytes:
    """
    Minimal: Skip to palette 4 and write 8 bytes of RED.
    """
    code = bytearray()

    # Set OCPS to palette 4 start (4 * 8 = 32 = 0x20)
    # With auto-increment: 0x80 | 0x20 = 0xA0
    code.extend([0x3E, 0xA0])        # LD A, 0xA0 (auto-inc + palette 4)
    code.extend([0xE0, 0x6A])        # LDH [OCPS], A

    # Write 8 hardcoded bytes for RED palette
    # Color 0: 00 00 (trans)
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 1: 1F 00 (RED)
    code.extend([0x3E, 0x1F])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 2: 0F 00 (dark red)
    code.extend([0x3E, 0x0F])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 3: 00 00 (black)
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])

    code.append(0xC9)
    return bytes(code)


def create_loop_palette_loader() -> bytes:
    """
    Same RED palette but using a loop to read from inline data.
    """
    code = bytearray()

    # Jump over inline data (8 bytes)
    code.extend([0x18, 0x08])  # JR +8

    # Inline RED palette data
    red_data_offset = len(code)
    code.extend([0x00, 0x00])  # trans
    code.extend([0x1F, 0x00])  # RED
    code.extend([0x0F, 0x00])  # dark red
    code.extend([0x00, 0x00])  # black

    # Loader code starts here
    # Set OCPS to palette 4 (0xA0)
    code.extend([0x3E, 0xA0])
    code.extend([0xE0, 0x6A])

    # HL = address of inline data (0x6800 + 2)
    data_addr = 0x6800 + red_data_offset
    code.extend([0x21, data_addr & 0xFF, (data_addr >> 8) & 0xFF])

    # Loop: write 8 bytes
    code.extend([0x0E, 0x08])  # LD C, 8
    loop_start = len(code)
    code.append(0x2A)          # LD A, [HL+]
    code.extend([0xE0, 0x6B])  # LDH [OCPD], A
    code.append(0x0D)          # DEC C
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])

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

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Build MINIMAL version first (hardcoded RED, no loop)
    print("=== Building MINIMAL (hardcoded, no loop) ===")
    palette_loader_addr = 0x6800
    colorizer_addr = 0x6830
    shadow_main_addr = 0x6850
    combined_addr = 0x6880

    minimal_loader = create_minimal_palette_loader()
    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Minimal loader: {len(minimal_loader)} bytes")

    bank13_offset = 13 * 0x4000
    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_loader_addr, minimal_loader)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    Path("rom/working/penta_dragon_dx_MINIMAL.gb").write_bytes(rom)
    print("Wrote: rom/working/penta_dragon_dx_MINIMAL.gb")

    # Build LOOP version (same RED, but via loop)
    print("\n=== Building LOOP (same RED, via loop) ===")
    rom2 = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom2)

    loop_loader = create_loop_palette_loader()
    print(f"Loop loader: {len(loop_loader)} bytes")

    def write_to_bank13_2(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom2[offset:offset + len(data)] = data

    write_to_bank13_2(palette_loader_addr, loop_loader)
    write_to_bank13_2(colorizer_addr, colorizer)
    write_to_bank13_2(shadow_main_addr, shadow_main)
    write_to_bank13_2(combined_addr, combined)

    rom2[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom2[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom2[0x143] = 0x80

    Path("rom/working/penta_dragon_dx_LOOP.gb").write_bytes(rom2)
    print("Wrote: rom/working/penta_dragon_dx_LOOP.gb")

    print("\nTest both - if MINIMAL is RED and LOOP is NOT, the loop is broken")


if __name__ == "__main__":
    main()
