#!/usr/bin/env python3
"""
v1.56: Fixed crash + improved BG tile mapping

Fixes from v1.55:
1. CRASH FIX: Use JP instead of RST 08 at 0x4003
   - RST pushes return address (0x4004) which corrupts stack
   - JP doesn't push anything, preserving the original call chain

2. VISUAL FIX: Improved tile->palette mapping
   - More tiles mapped to floor (palette 0) instead of walls (palette 2)
   - Only specific wall tiles get purple
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
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

    boss_data = data.get('boss_palettes', {})
    gargoyle = pal_to_bytes(boss_data.get('Gargoyle', {}).get('colors', ["0000", "601F", "400F", "0000"]))
    spider = pal_to_bytes(boss_data.get('Spider', {}).get('colors', ["0000", "001F", "00BF", "0000"]))

    return bytes(bg_data), bytes(obj_data), gargoyle, spider


def create_bg_tile_lookup_table() -> bytes:
    """
    256-byte lookup table: tile ID -> BG palette number.

    Improved mapping - most tiles should be floor (palette 0),
    only specific ranges get different colors:
    - Palette 0 (blue): Floor, platforms, most tiles
    - Palette 1 (gold): Items/powerups (0xA0-0xDF)
    - Palette 2 (purple): Specific wall decorations only
    - Palette 5 (red): Hazards (spikes)
    """
    table = bytearray(256)

    for i in range(256):
        # Default to floor (palette 0)
        table[i] = 0x00

        # Items/powerups - gold (palette 1)
        if 0xA0 <= i < 0xE0:
            table[i] = 0x01

        # Hazards/spikes - red (palette 5)
        elif 0x4C <= i < 0x50:
            table[i] = 0x05

        # Specific wall tiles - purple (palette 2)
        # Only the clearly "wall" tiles, not platforms
        elif i in [0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x21, 0x22, 0x23]:
            table[i] = 0x02

    return bytes(table)


def create_trampoline_handler() -> bytes:
    """
    Handler at 0x0008 (8 bytes).
    Called via JP 0x0008 from patched 0x4003.
    Switches to bank 4 and jumps to our wrapper.
    """
    code = bytearray()
    # LD A, 4
    code.extend([0x3E, 0x04])
    # LD [0x2000], A
    code.extend([0xEA, 0x00, 0x20])
    # JP 0x7000
    code.extend([0xC3, 0x00, 0x70])
    assert len(code) == 8
    return bytes(code)


def create_vram_init_wrapper() -> bytes:
    """VRAM init wrapper at 0x7000 in bank 4."""
    code = bytearray()

    # Original code from 0x4003-0x400B
    code.extend([0x21, 0x00, 0x98])     # LD HL, 0x9800
    code.extend([0x01, 0x00, 0x10])     # LD BC, 0x1000
    code.extend([0xCD, 0xA8, 0x09])     # CALL 0x09A8 (memset in bank 0)

    # Initialize VRAM bank 1 to palette 0
    code.extend([0xC5, 0xD5, 0xE5])     # PUSH BC, DE, HL
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A
    code.extend([0x21, 0x00, 0x98])     # LD HL, 0x9800
    code.extend([0x01, 0x00, 0x04])     # LD BC, 0x0400
    code.extend([0x3E, 0x00])           # LD A, 0

    loop_start = len(code)
    code.append(0x77)                   # LD [HL], A
    code.append(0x23)                   # INC HL
    code.append(0x0B)                   # DEC BC
    code.append(0x78)                   # LD A, B
    code.append(0xB1)                   # OR C
    code.extend([0x3E, 0x00])           # LD A, 0
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])  # JR NZ, loop

    code.append(0xAF)                   # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A
    code.extend([0xAF])                 # XOR A
    code.extend([0xE0, 0xC0])           # LDH [0xFFC0], A (init row counter)
    code.extend([0xE1, 0xD1, 0xC1])     # POP HL, DE, BC

    # Switch back to bank 1 and continue original init
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xEA, 0x00, 0x20])     # LD [0x2000], A
    code.extend([0xC3, 0x0C, 0x40])     # JP 0x400C

    return bytes(code)


def create_bg_row_colorizer(lookup_table_addr: int) -> bytes:
    """BG row colorizer using WRAM buffer for 2-phase approach."""
    WRAM_BUFFER = 0xDFF0

    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Ensure VBK = 0
    code.append(0xAF)
    code.extend([0xE0, 0x4F])

    # Get row and calculate VRAM address
    code.extend([0xF0, 0xC0])
    code.append(0x47)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x87)
    code.append(0x6F)
    code.extend([0x26, 0x98])
    code.append(0x78)
    code.extend([0xE6, 0x18])
    code.append(0x0F)
    code.append(0x0F)
    code.append(0x0F)
    code.append(0x84)
    code.append(0x67)

    code.append(0xE5)  # PUSH HL (save VRAM addr)

    # Phase 1: Read tiles and look up palettes into WRAM buffer
    code.extend([0x11, WRAM_BUFFER & 0xFF, (WRAM_BUFFER >> 8) & 0xFF])
    code.extend([0x0E, 0x20])

    read_loop = len(code)
    code.append(0x7E)  # LD A, [HL]
    code.append(0xE5)  # PUSH HL
    code.append(0x6F)  # LD L, A
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])
    code.append(0x7E)  # LD A, [HL]
    code.append(0xE1)  # POP HL
    code.append(0x12)  # LD [DE], A
    code.append(0x13)  # INC DE
    code.append(0x23)  # INC HL
    code.append(0x0D)  # DEC C
    offset = read_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # Phase 2: Switch to VBK=1 and copy buffer to VRAM
    code.extend([0x3E, 0x01])
    code.extend([0xE0, 0x4F])
    code.append(0xE1)  # POP HL (VRAM addr)
    code.extend([0x11, WRAM_BUFFER & 0xFF, (WRAM_BUFFER >> 8) & 0xFF])
    code.extend([0x0E, 0x20])

    write_loop = len(code)
    code.append(0x1A)  # LD A, [DE]
    code.append(0x77)  # LD [HL], A
    code.append(0x13)  # INC DE
    code.append(0x23)  # INC HL
    code.append(0x0D)  # DEC C
    offset = write_loop - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # Switch back to VBK=0, increment row counter
    code.append(0xAF)
    code.extend([0xE0, 0x4F])
    code.extend([0xF0, 0xC0])
    code.append(0x3C)
    code.extend([0xE6, 0x1F])
    code.extend([0xE0, 0xC0])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_tile_based_colorizer() -> bytes:
    """Sprite colorizer (same as v1.09)."""
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    code.extend([0x06, 0x28])
    labels['loop_start'] = len(code)
    code.extend([0x3E, 0x28])
    code.append(0x90)
    code.extend([0xFE, 0x04])
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])
    code.append(0x2B)
    code.append(0x7E)
    code.append(0x23)
    code.append(0x4F)
    code.extend([0xFE, 0x10])
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])
    code.append(0x7B)
    code.append(0xB7)
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])
    code.append(0x79)
    code.extend([0xFE, 0x50])
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x60])
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x70])
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])
    code.extend([0xFE, 0x80])
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])
    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['check_hornet'] = len(code)
    code.append(0x79)
    code.extend([0xFE, 0x40])
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['sara_palette'] = len(code)
    code.append(0x7A)
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['boss_palette'] = len(code)
    code.extend([0x3E, 0x07])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])
    labels['apply_palette'] = len(code)
    code.append(0x4F)
    code.append(0x7E)
    code.extend([0xE6, 0xF8])
    code.append(0xB1)
    code.append(0x77)
    code.extend([0x23, 0x23, 0x23, 0x23])
    code.append(0x05)
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])
    code.append(0xC9)

    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])
    code.extend([0xF0, 0xBE])
    code.append(0xB7)
    code.extend([0x20, 0x04])
    code.extend([0x16, 0x02])
    code.extend([0x18, 0x02])
    code.extend([0x16, 0x01])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x28, 0x08])
    code.extend([0xFE, 0x02])
    code.extend([0x28, 0x06])
    code.extend([0x1E, 0x00])
    code.extend([0x18, 0x06])
    code.extend([0x1E, 0x06])
    code.extend([0x18, 0x02])
    code.extend([0x1E, 0x07])
    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)
    return bytes(code)


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    code = bytearray()
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x0E, 0x40])
    code.extend([0x2A])
    code.extend([0xE0, 0x69])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x30])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])
    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x03])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])
    code.append(0xC9)
    return bytes(code)


def create_combined_with_dma_and_bg(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
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
    output_rom = Path("rom/working/penta_dragon_dx_v156.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.56: Crash Fix + Improved BG Mapping ===")
    print("  FIX: Use JP instead of RST (no stack corruption)")
    print("  FIX: Better tile->palette mapping (less purple)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Trampoline handler at 0x0008
    trampoline = create_trampoline_handler()
    print(f"Trampoline handler: {len(trampoline)} bytes at 0x0008")
    rom[0x0008:0x0008 + len(trampoline)] = trampoline

    # Patch 0x4003 with JP 0x0008 (not RST!)
    print(f"Original at 0x4003: {rom[0x4003:0x400C].hex()}")
    rom[0x4003] = 0xC3  # JP
    rom[0x4004] = 0x08  # low byte
    rom[0x4005] = 0x00  # high byte
    # NOP out 0x4006-0x400B
    for i in range(0x4006, 0x400C):
        rom[i] = 0x00
    print(f"Patched 0x4003: C3 08 00 (JP 0x0008) + NOPs")

    # VRAM init wrapper in bank 4
    vram_init_wrapper = create_vram_init_wrapper()
    bank4_offset = 4 * 0x4000
    wrapper_rom_offset = bank4_offset + (0x7000 - 0x4000)
    print(f"VRAM init wrapper: {len(vram_init_wrapper)} bytes at ROM 0x{wrapper_rom_offset:05X}")
    rom[wrapper_rom_offset:wrapper_rom_offset + len(vram_init_wrapper)] = vram_init_wrapper

    # Lookup table and other code in bank 13
    lookup_table = create_bg_tile_lookup_table()
    lookup_table_addr = 0x6B00

    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    bg_colorizer_addr = 0x6A40
    combined_addr = 0x6AC0

    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_colorizer = create_bg_row_colorizer(lookup_table_addr)
    combined = create_combined_with_dma_and_bg(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"BG lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")

    bank13_offset = 13 * 0x4000

    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    rom[bank13_offset + (colorizer_addr - 0x4000):bank13_offset + (colorizer_addr - 0x4000) + len(colorizer)] = colorizer
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (bg_colorizer_addr - 0x4000):bank13_offset + (bg_colorizer_addr - 0x4000) + len(bg_colorizer)] = bg_colorizer
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined
    rom[bank13_offset + (lookup_table_addr - 0x4000):bank13_offset + (lookup_table_addr - 0x4000) + len(lookup_table)] = lookup_table

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.56 Build Complete ===")


if __name__ == "__main__":
    main()
