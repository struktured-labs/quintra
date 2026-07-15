#!/usr/bin/env python3
"""
Test: Loop-based palette loading with DI/EI to disable interrupts.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_obj_palette_data(yaml_path: Path) -> bytes:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors: list[str]) -> bytes:
        result = bytearray()
        for c in colors:
            val = int(c, 16) & 0x7FFF
            result.extend([val & 0xFF, (val >> 8) & 0xFF])
        return bytes(result)

    obj_keys = ['Effects', 'SaraDragon', 'SaraWitch', 'Crow',
                'Hornets', 'OrcGround', 'Humanoid', 'Catfish']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

    return bytes(obj_data)


def create_loop_with_di_loader(obj_data_addr: int) -> bytes:
    """OBJ palettes using loop with DI/EI."""
    code = bytearray()

    # DISABLE INTERRUPTS
    code.append(0xF3)  # DI

    # Load OBJ palettes from ROM
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])        # OCPS = 0x80
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x40])        # 64 bytes
    loop_start = len(code)
    code.append(0x2A)                # LD A, [HL+]
    code.extend([0xE0, 0x6B])        # LDH [OCPD], A
    code.append(0x0D)                # DEC C
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # RE-ENABLE INTERRUPTS
    code.append(0xFB)  # EI

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
    output_rom = Path("rom/working/penta_dragon_dx_LOOPDI.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print("=== Loop with DI/EI (interrupts disabled) ===")

    obj_data = load_obj_palette_data(palette_path)

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    obj_data_addr = 0x6800
    palette_loader_addr = 0x6850
    colorizer_addr = 0x6880
    shadow_main_addr = 0x68A0
    combined_addr = 0x68D0

    palette_loader = create_loop_with_di_loader(obj_data_addr)
    colorizer = create_force_palette4_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook(combined_addr)

    print(f"Palette loader: {len(palette_loader)} bytes")

    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(obj_data_addr, obj_data)
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
