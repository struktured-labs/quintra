#!/usr/bin/env python3
"""
v2.07: Minimal VBK Test + Visual Indicator

Absolute minimal test: just write palette 2 to first 32 VRAM attributes
and ALSO change BG palette 2 to bright green as a visual indicator.

If we see green tiles, VBK 1 writes ARE working.
If we don't see green but see the rest of the game colored (sprites),
then VBK writes specifically aren't working from savestate.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_minimal_vbk_and_palette_test() -> bytes:
    """
    Minimal test that:
    1. Sets BG palette 2 to bright green via BCPS/BCPD
    2. Writes palette 2 to first 32 bytes of VBK 1 VRAM

    If green appears in top row, VBK works!
    """
    code = bytearray()

    # === PART 1: Set BG palette 2 to BRIGHT GREEN ===
    # Palette 2 starts at index 16 (8 bytes per palette × 2)
    code.extend([0x3E, 0x90])              # LD A, 0x90 (palette 2, color 0, auto-inc)
    code.extend([0xE0, 0x68])              # LDH [BCPS], A

    # Write 4 green colors (8 bytes total)
    # Color format: BGR555, Green = 0x03E0
    for _ in range(4):
        code.extend([0x3E, 0xE0])          # LD A, 0xE0 (low byte of green)
        code.extend([0xE0, 0x69])          # LDH [BCPD], A
        code.extend([0x3E, 0x03])          # LD A, 0x03 (high byte of green)
        code.extend([0xE0, 0x69])          # LDH [BCPD], A

    # === PART 2: Switch to VBK 1 and write palette 2 to first row ===
    code.extend([0x3E, 0x01])              # LD A, 1
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    code.extend([0x21, 0x00, 0x98])        # LD HL, 0x9800
    code.extend([0x3E, 0x02])              # LD A, 2 (palette 2 = green)
    code.extend([0x06, 0x20])              # LD B, 32 (first row)

    # write_loop:
    write_loop = len(code)
    code.append(0x77)                      # LD [HL], A
    code.append(0x23)                      # INC HL
    code.append(0x05)                      # DEC B
    offset = write_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])     # JR NZ, write_loop

    # Switch back to VBK 0
    code.extend([0xAF])                    # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    code.append(0xC9)                      # RET

    return bytes(code)


def create_simple_combined(test_addr: int) -> bytes:
    """Just call the test and then sprite DMA."""
    code = bytearray()
    code.extend([0xCD, test_addr & 0xFF, test_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])        # Sprite DMA
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
    output_rom = Path("rom/working/penta_dragon_dx_v207.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")

    print("\n=== v2.07: Minimal VBK + Green Palette Test ===")
    print("  1. Sets BG palette 2 to BRIGHT GREEN")
    print("  2. Writes palette 2 to first row of VBK 1")
    print("  Expected: TOP ROW should be GREEN if VBK works")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    test_addr = 0x6900
    combined_addr = 0x6980

    test_code = create_minimal_vbk_and_palette_test()
    combined = create_simple_combined(test_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Test code: {len(test_code)} bytes at 0x{test_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    bank13_offset = 13 * 0x4000

    def bank_offset(addr):
        return bank13_offset + (addr - 0x4000)

    rom[bank_offset(test_addr):bank_offset(test_addr) + len(test_code)] = test_code
    rom[bank_offset(combined_addr):bank_offset(combined_addr) + len(combined)] = combined

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v2.07 Build Complete ===")


if __name__ == "__main__":
    main()
