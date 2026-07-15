#!/usr/bin/env python3
"""
Diagnostic: Embed palette data inline with code (data immediately after loop).
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


def create_inline_palette_loader(bg_data: bytes, obj_data: bytes, base_addr: int) -> bytes:
    """
    Creates code with palette data embedded inline.
    Uses PC-relative addressing to find the data.

    Layout:
    - Code that jumps over data
    - BG palette data (64 bytes)
    - OBJ palette data (64 bytes)
    - Actual loader code
    """
    code = bytearray()

    # Jump over the embedded data
    # Data is 128 bytes, we need to jump past it
    data_size = len(bg_data) + len(obj_data)  # 128 bytes
    # JR offset calculation: we want to jump to the code after the data
    # Current position after JR instruction: base_addr + 2
    # Data starts at: base_addr + 2
    # Data ends at: base_addr + 2 + 128 = base_addr + 130
    # We want to jump to base_addr + 130
    # JR offset = 128
    code.extend([0x18, data_size])  # JR +128

    # Embed BG palette data here
    bg_data_offset = len(code)
    code.extend(bg_data)

    # Embed OBJ palette data here
    obj_data_offset = len(code)
    code.extend(obj_data)

    # Now the actual loader code
    loader_start = len(code)

    # Calculate absolute addresses for the embedded data
    bg_addr = base_addr + bg_data_offset
    obj_addr = base_addr + obj_data_offset

    # Load BG palettes
    code.extend([0x21, bg_addr & 0xFF, (bg_addr >> 8) & 0xFF])  # LD HL, bg_addr
    code.extend([0x3E, 0x80])        # LD A, 0x80
    code.extend([0xE0, 0x68])        # LDH [BCPS], A
    code.extend([0x0E, 0x40])        # LD C, 64
    bg_loop = len(code)
    code.append(0x2A)                # LD A, [HL+]
    code.extend([0xE0, 0x69])        # LDH [BCPD], A
    code.append(0x0D)                # DEC C
    bg_offset = bg_loop - len(code) - 2
    code.extend([0x20, bg_offset & 0xFF])

    # Load OBJ palettes
    code.extend([0x21, obj_addr & 0xFF, (obj_addr >> 8) & 0xFF])  # LD HL, obj_addr
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
    output_rom = Path("rom/working/penta_dragon_dx_INLINE.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print("=== DIAGNOSTIC: Inline palette data ===")
    print("Data embedded directly in code section")
    print()

    bg_data, obj_data = load_palettes_from_yaml(palette_path)

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Addresses
    colorizer_addr = 0x6800
    shadow_main_addr = 0x6820
    palette_loader_addr = 0x6850  # Data + code together
    combined_addr = 0x6950

    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_inline_palette_loader(bg_data, obj_data, palette_loader_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader (with data): {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

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

    # Verify data placement
    print(f"\nData verification:")
    print(f"  BG data at ROM offset 0x{bank13_offset + (palette_loader_addr - 0x4000) + 2:05X}")
    print(f"  OBJ data at ROM offset 0x{bank13_offset + (palette_loader_addr - 0x4000) + 2 + 64:05X}")


if __name__ == "__main__":
    main()
