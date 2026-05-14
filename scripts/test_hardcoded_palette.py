#!/usr/bin/env python3
"""
Diagnostic: Hardcode palette values directly (no loop, no memory reads).
This tests if the OCPS/OCPD registers work at all.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_hardcoded_palette_loader() -> bytes:
    """
    Load palettes using HARDCODED immediate values.
    Sets OBJ palette 4 to pure red (0x001F) for visibility testing.
    """
    code = bytearray()

    # Load BG palettes with simple grayscale
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, start at 0)
    code.extend([0xE0, 0x68])        # LDH [BCPS], A

    # Write 64 bytes of grayscale (palette 0-7 all white->gray->dark->black)
    for i in range(8):  # 8 palettes
        # Color 0: White 0x7FFF
        code.extend([0x3E, 0xFF])    # LD A, 0xFF
        code.extend([0xE0, 0x69])    # LDH [BCPD], A
        code.extend([0x3E, 0x7F])    # LD A, 0x7F
        code.extend([0xE0, 0x69])    # LDH [BCPD], A
        # Color 1: Light gray 0x5294
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x69])
        # Color 2: Dark gray 0x294A
        code.extend([0x3E, 0x4A])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x29])
        code.extend([0xE0, 0x69])
        # Color 3: Black 0x0000
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x69])

    # Load OBJ palettes
    code.extend([0x3E, 0x80])        # LD A, 0x80 (auto-increment, start at 0)
    code.extend([0xE0, 0x6A])        # LDH [OCPS], A

    # Palettes 0-3: Simple gray
    for i in range(4):
        # Color 0: Trans
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        # Color 1: White
        code.extend([0x3E, 0xFF])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x7F])
        code.extend([0xE0, 0x6B])
        # Color 2: Gray
        code.extend([0x3E, 0x94])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x52])
        code.extend([0xE0, 0x6B])
        # Color 3: Dark
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])
        code.extend([0x3E, 0x00])
        code.extend([0xE0, 0x6B])

    # Palette 4: PURE RED (0x001F) for testing!
    # Color 0: Trans
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 1: RED 0x001F
    code.extend([0x3E, 0x1F])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 2: Dark RED 0x000F
    code.extend([0x3E, 0x0F])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    # Color 3: Black
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])
    code.extend([0x3E, 0x00])
    code.extend([0xE0, 0x6B])

    # Palettes 5-7: Gray
    for i in range(3):
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

    code.append(0xC9)                # RET

    return bytes(code)


def create_force_palette4_colorizer() -> bytes:
    """Force ALL sprites to palette 4."""
    code = bytearray()
    code.extend([0x06, 0x28])        # LD B, 40
    loop_start = len(code)
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.extend([0xF6, 0x04])        # OR 0x04
    code.append(0x77)                # LD [HL], A
    code.extend([0x23, 0x23, 0x23, 0x23])
    code.append(0x05)
    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """Colorize both shadow buffers."""
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
    output_rom = Path("rom/working/penta_dragon_dx_HARDCODED.gb")

    print("=== DIAGNOSTIC: Hardcoded RED palette 4 ===")
    print("Writes palette values directly without memory loops.")
    print("If sprites turn RED -> OCPS/OCPD registers work")
    print("If sprites stay gray/blue -> Something fundamentally broken")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    colorizer_addr = 0x6800
    shadow_main_addr = 0x6820
    palette_loader_addr = 0x6850
    combined_addr = 0x6B00

    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_hardcoded_palette_loader()
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Check for overlaps
    if shadow_main_addr + len(shadow_main) > palette_loader_addr:
        print("WARNING: shadow_main overlaps palette_loader!")
    if palette_loader_addr + len(palette_loader) > combined_addr:
        print(f"WARNING: palette_loader ends at 0x{palette_loader_addr + len(palette_loader):04X}, combined starts at 0x{combined_addr:04X}")

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

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
