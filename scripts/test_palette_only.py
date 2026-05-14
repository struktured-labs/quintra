#!/usr/bin/env python3
"""
MINIMAL test: ONLY palette loading, nothing else.
No colorizer, no shadow OAM, no DMA.
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


def create_minimal_vblank_hook_with_loop(bank0_data_addr: int) -> bytes:
    """
    MINIMAL VBlank hook: just input reading + loop-based palette load.
    No extra function calls, no colorizer, no DMA.
    """
    code = bytearray()

    # Original input reading (preserved from original ROM)
    code.extend([
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
    ])

    # INLINE palette loading - no CALL, directly here
    # Point HL to bank 0 data
    code.extend([0x21, bank0_data_addr & 0xFF, (bank0_data_addr >> 8) & 0xFF])

    # Set OCPS to 0x80
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])

    # Loop 64 bytes
    code.extend([0x0E, 0x40])  # LD C, 64
    loop_start = len(code)
    code.append(0x2A)          # LD A, [HL+]
    code.extend([0xE0, 0x6B])  # LDH [OCPD], A
    code.append(0x0D)          # DEC C
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    code.append(0xC9)  # RET
    return bytes(code)


def create_minimal_vblank_hook_hardcoded() -> bytes:
    """
    MINIMAL VBlank hook with HARDCODED RED palette.
    """
    code = bytearray()

    # Original input reading
    code.extend([
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00, 0xF0, 0x00, 0xF0, 0x00, 0x2F, 0xE6, 0x0F, 0xB0,
        0xE0, 0x93, 0x3E, 0x30, 0xE0, 0x00,
    ])

    # INLINE hardcoded palette loading
    # Set OCPS to 0x80
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])

    # Write all 64 bytes hardcoded (palettes 0-7)
    # Each palette: trans, color1, color2, color3 (4 colors x 2 bytes = 8 bytes)
    for pal in range(8):
        if pal == 4:
            # Palette 4: RED
            colors = [(0x00, 0x00), (0x1F, 0x00), (0x0F, 0x00), (0x00, 0x00)]
        else:
            # Others: gray
            colors = [(0x00, 0x00), (0xFF, 0x7F), (0x94, 0x52), (0x00, 0x00)]

        for lo, hi in colors:
            code.extend([0x3E, lo])
            code.extend([0xE0, 0x6B])
            code.extend([0x3E, hi])
            code.extend([0xE0, 0x6B])

    code.append(0xC9)
    return bytes(code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    obj_data = load_obj_palette_data(palette_path)

    # Build LOOP version
    print("=== Building PALETTE_ONLY_LOOP ===")
    rom1 = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom1)

    bank0_data_addr = 0x0200
    rom1[bank0_data_addr:bank0_data_addr + len(obj_data)] = obj_data

    vblank_hook_loop = create_minimal_vblank_hook_with_loop(bank0_data_addr)
    print(f"VBlank hook (loop): {len(vblank_hook_loop)} bytes")

    rom1[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom1[0x0824:0x0824 + len(vblank_hook_loop)] = vblank_hook_loop
    rom1[0x143] = 0x80

    Path("rom/working/penta_dragon_dx_PALONLY_LOOP.gb").write_bytes(rom1)
    print("Wrote: rom/working/penta_dragon_dx_PALONLY_LOOP.gb")

    # Build HARDCODED version
    print("\n=== Building PALETTE_ONLY_HARDCODED ===")
    rom2 = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom2)

    vblank_hook_hard = create_minimal_vblank_hook_hardcoded()
    print(f"VBlank hook (hardcoded): {len(vblank_hook_hard)} bytes")

    rom2[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom2[0x0824:0x0824 + len(vblank_hook_hard)] = vblank_hook_hard
    rom2[0x143] = 0x80

    Path("rom/working/penta_dragon_dx_PALONLY_HARD.gb").write_bytes(rom2)
    print("Wrote: rom/working/penta_dragon_dx_PALONLY_HARD.gb")

    print("\nTest both - if HARD is RED and LOOP is NOT, the loop is broken")


if __name__ == "__main__":
    main()
