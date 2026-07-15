#!/usr/bin/env python3
"""
v1.45: One-Time BG Colorization

Colorizes all 576 BG tiles ONCE across 18 frames, then stops.

Uses counter at 0xFFC2:
- 0-17: Colorize chunk N (32 tiles), increment counter
- 18+: DONE - skip BG colorization entirely

This avoids per-frame VRAM bank switching after initial setup.
Should eliminate flickering while still providing BG colors.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
    """Load BG, OBJ, and boss palettes from YAML file."""
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


def create_tile_palette_lookup() -> bytes:
    """256-byte lookup table: tile ID -> BG palette (0-7).

    BG Palette mapping (from YAML):
      0 = Dungeon (blue/white floor)
      1 = BG1 (GOLD/YELLOW - items)
      2 = BG2 (purple/magenta)
      3 = BG3 (green - nature/hazards)
      4 = BG4 (cyan)
      5 = BG5 (fire red/orange - danger)
      6 = BG6 (blue-gray stone)
      7 = BG7 (deep blue)
    """
    lookup = bytearray(256)

    for i in range(256):
        if i <= 0x02:
            lookup[i] = 0  # Floor - blue/white
        elif i <= 0x04:
            lookup[i] = 2  # Walls - purple
        elif i <= 0x0F:
            lookup[i] = 6  # Platforms - blue-gray stone
        elif i <= 0x1F:
            lookup[i] = 0  # Deco - floor color
        elif i <= 0x2F:
            lookup[i] = 6  # Deco - stone
        elif i <= 0x4B:
            lookup[i] = 2  # Structure - purple
        elif i <= 0x4D:
            lookup[i] = 5  # Hazards - fire red/orange
        elif i <= 0x7F:
            lookup[i] = 2  # Extended walls - purple
        elif i <= 0x9F:
            lookup[i] = 5  # Hazards - fire red/orange
        elif i <= 0xDF:
            lookup[i] = 1  # Items - GOLD/YELLOW
        elif i <= 0xFE:
            lookup[i] = 2  # Borders - purple
        else:
            lookup[i] = 0  # Empty - floor

    return bytes(lookup)


def create_tile_based_colorizer() -> bytes:
    """Sprite colorizer (unchanged from v1.09)."""
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
    """Colorizes BOTH shadow buffers."""
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


def create_bg_colorizer_onetime(lookup_table_addr: int, frame_counter_addr: int) -> bytes:
    """
    ONE-TIME BG colorizer - runs for 18 frames then stops forever.

    Uses counter at 0xFFC2:
    - If counter >= 18: SKIP (already done)
    - If counter < 18: Colorize chunk, increment counter

    After 18 frames, all 576 tiles are colored and we never touch VRAM bank 1 again.
    """
    code = bytearray()

    # Check if already done (counter >= 18)
    code.extend([0xF0, frame_counter_addr & 0xFF])  # LDH A, [counter]
    code.extend([0xFE, 0x12])           # CP 18
    code.extend([0xD0])                 # RET NC (return if >= 18, already done)

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Switch to VRAM bank 1
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Get frame counter and calculate offset
    code.extend([0xF0, frame_counter_addr & 0xFF])  # LDH A, [counter]

    # Multiply by 32: shift left 5 times
    code.append(0x6F)                   # LD L, A
    code.extend([0x26, 0x00])           # LD H, 0
    code.append(0x29)                   # ADD HL, HL (x2)
    code.append(0x29)                   # x4
    code.append(0x29)                   # x8
    code.append(0x29)                   # x16
    code.append(0x29)                   # x32
    # HL = offset (0, 32, 64, ..., 544)

    # Store offset on stack for later
    code.append(0xE5)                   # PUSH HL

    # Calculate VRAM dest = 0x9800 + offset -> store in DE
    code.extend([0x01, 0x00, 0x98])     # LD BC, 0x9800
    code.append(0x09)                   # ADD HL, BC (HL = VRAM dest)
    code.append(0x54)                   # LD D, H
    code.append(0x5D)                   # LD E, L
    # DE = VRAM dest

    # Calculate tile buffer src = 0xC1A0 + offset
    code.append(0xE1)                   # POP HL (get offset back)
    code.extend([0x01, 0xA0, 0xC1])     # LD BC, 0xC1A0
    code.append(0x09)                   # ADD HL, BC
    # HL = tile buffer src, DE = VRAM dest

    # Process 32 tiles
    code.extend([0x0E, 0x20])           # LD C, 32

    loop_start = len(code)
    code.append(0x7E)                   # LD A, [HL] - get tile ID
    code.append(0x23)                   # INC HL
    code.append(0xE5)                   # PUSH HL

    # Lookup palette
    code.extend([0x26, (lookup_table_addr >> 8) & 0xFF])  # LD H, lookup_high
    code.append(0x6F)                   # LD L, A
    code.append(0x7E)                   # LD A, [HL] - get palette

    code.append(0xE1)                   # POP HL

    # Write to VRAM bank 1
    code.append(0x12)                   # LD [DE], A
    code.append(0x13)                   # INC DE

    code.append(0x0D)                   # DEC C
    jump_offset = loop_start - len(code) - 2
    code.extend([0x20, jump_offset & 0xFF])  # JR NZ, loop

    # Increment counter (NO wrap - let it stay at 18+ forever)
    code.extend([0xF0, frame_counter_addr & 0xFF])  # LDH A, [counter]
    code.append(0x3C)                   # INC A
    code.extend([0xE0, frame_counter_addr & 0xFF])  # LDH [counter], A

    # Switch back to VRAM bank 0
    code.append(0xAF)                   # XOR A
    code.extend([0xE0, 0x4F])           # LDH [VBK], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)                   # RET

    return bytes(code)


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes."""
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


def create_combined_with_bg(palette_loader_addr: int, shadow_main_addr: int,
                             bg_colorizer_addr: int) -> bytes:
    """Combined function."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v145.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.45: One-Time BG Colorization ===")
    print("  Colorizes 576 tiles across first 18 frames")
    print("  Then STOPS - no more VRAM bank switching")
    print("  Should eliminate flickering")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    bg_colorizer_addr = 0x6A40
    combined_addr = 0x6AC0
    lookup_table_addr = 0x6B00
    frame_counter_addr = 0xC2  # HRAM

    # Generate code
    lookup_table = create_tile_palette_lookup()
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_colorizer = create_bg_colorizer_onetime(lookup_table_addr, frame_counter_addr)
    combined = create_combined_with_bg(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")
    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(gargoyle_addr, gargoyle)
    write_to_bank13(spider_addr, spider)
    write_to_bank13(lookup_table_addr, lookup_table)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(bg_colorizer_addr, bg_colorizer)
    write_to_bank13(combined_addr, combined)

    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.45 Build Complete ===")


if __name__ == "__main__":
    main()
