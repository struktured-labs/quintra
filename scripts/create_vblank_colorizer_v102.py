#!/usr/bin/env python3
"""
v1.02: Post-copy palette hook for flicker elimination.

The game has a sprite update routine at 0x1ED5 that ends by copying
0xC000 to 0xC100 via memcpy at 0x1F0C. By hooking this memcpy call,
we can inject palette data AFTER the game finishes updating sprites,
eliminating the race condition that caused partial colorization.

Hook strategy:
1. Put a trampoline at 0x0834 (free space after VBlank trampoline)
2. Modify 0x1F0C to call our trampoline instead of 0x09B3
3. Trampoline: call memcpy, switch to bank 13, set palettes, return

This ensures palettes are set after EVERY sprite update, not just in VBlank.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_tile_palette_table() -> bytes:
    """Create 256-byte tile-to-palette lookup table."""
    table = bytearray(256)

    for tile in range(256):
        if tile < 0x20:
            table[tile] = 0  # Effects
        elif tile < 0x30:
            table[tile] = 2  # Sara (form determined by 0xFFBE)
        elif tile < 0x40:
            table[tile] = 3  # Crow (dark blue)
        elif tile < 0x50:
            table[tile] = 4  # Hornets (yellow)
        elif tile < 0x60:
            table[tile] = 5  # Orc/Ground (green)
        elif tile < 0x70:
            table[tile] = 6  # Humanoid (purple)
        elif tile < 0x80:
            table[tile] = 7  # Catfish (cyan)
        else:
            table[tile] = 4  # Default

    return bytes(table)


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes]:
    """Load palettes from YAML file."""
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


def create_buffer_colorizer(tile_table_addr: int) -> bytes:
    """
    Colorize BOTH shadow OAM buffers (0xC000 and 0xC100).
    Called after the game's memcpy, so both buffers have identical sprite data.
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # === Determine Sara palette (store in D) ===
    code.extend([0xF0, 0xBE])        # LDH A, [0xFFBE]
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x04])        # JR NZ, +4 (Sara D)
    code.extend([0x16, 0x02])        # LD D, 2 (Sara W)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x16, 0x01])        # LD D, 1 (Sara D)

    # === Determine boss mode (store in E) ===
    code.extend([0xF0, 0xBF])        # LDH A, [0xFFBF]
    code.append(0xB7)                # OR A
    code.extend([0x28, 0x0C])        # JR Z, +12 (no boss)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x38, 0x04])        # JR C, +4 (Gargoyle)
    code.extend([0x1E, 0x07])        # LD E, 7 (Spider)
    code.extend([0x18, 0x06])        # JR +6
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x1E, 0x00])        # LD E, 0 (no boss)

    table_low = tile_table_addr & 0xFF
    table_high = (tile_table_addr >> 8) & 0xFF

    # === Process 0xC000 (40 sprites) ===
    code.extend([0x21, 0x00, 0xC0])  # LD HL, 0xC000
    code.extend([0x06, 0x28])        # LD B, 40

    loop1_start = len(code)

    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B
    code.extend([0xFE, 0x04])        # CP 4
    code.extend([0x30, 0x03])        # JR NC, +3 (enemy)

    code.append(0x7A)                # LD A, D (Sara palette)
    code.extend([0x18, 0x12])        # JR +18

    code.append(0x7B)                # LD A, E (boss check)
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x0E])        # JR NZ, +14 (use boss palette)

    # Tile lookup
    code.append(0xE5)                # PUSH HL
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x7E)                # LD A, [HL] (tile)
    code.extend([0xC6, table_low])   # ADD A, table_low
    code.append(0x6F)                # LD L, A
    code.extend([0x3E, table_high])  # LD A, table_high
    code.extend([0xCE, 0x00])        # ADC A, 0
    code.append(0x67)                # LD H, A
    code.append(0x7E)                # LD A, [HL] (palette)
    code.append(0xE1)                # POP HL

    # Apply palette
    code.append(0x4F)                # LD C, A
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A
    code.append(0x23)                # INC HL
    code.append(0x05)                # DEC B

    loop1_offset = loop1_start - len(code) - 2
    code.extend([0x20, loop1_offset & 0xFF])

    # === Process 0xC100 (40 sprites) ===
    code.extend([0x21, 0x00, 0xC1])  # LD HL, 0xC100
    code.extend([0x06, 0x28])        # LD B, 40

    loop2_start = len(code)

    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B
    code.extend([0xFE, 0x04])        # CP 4
    code.extend([0x30, 0x03])        # JR NC, +3

    code.append(0x7A)                # LD A, D
    code.extend([0x18, 0x12])        # JR +18

    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x0E])        # JR NZ, +14

    code.append(0xE5)                # PUSH HL
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xC6, table_low])   # ADD A, table_low
    code.append(0x6F)                # LD L, A
    code.extend([0x3E, table_high])  # LD A, table_high
    code.extend([0xCE, 0x00])        # ADC A, 0
    code.append(0x67)                # LD H, A
    code.append(0x7E)                # LD A, [HL]
    code.append(0xE1)                # POP HL

    code.append(0x4F)                # LD C, A
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x23)                # INC HL
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A
    code.append(0x23)                # INC HL
    code.append(0x05)                # DEC B

    loop2_offset = loop2_start - len(code) - 2
    code.extend([0x20, loop2_offset & 0xFF])

    # Restore and return
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                # RET

    return bytes(code)


def create_vblank_oam_colorizer(tile_table_addr: int) -> bytes:
    """
    VBlank OAM colorizer - only processes hardware OAM (0xFE00).
    The shadow buffers are handled by the post-copy hook.
    """
    code = bytearray()

    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Sara palette
    code.extend([0xF0, 0xBE])
    code.append(0xB7)
    code.extend([0x20, 0x04])
    code.extend([0x16, 0x02])
    code.extend([0x18, 0x02])
    code.extend([0x16, 0x01])

    # Boss mode
    code.extend([0xF0, 0xBF])
    code.append(0xB7)
    code.extend([0x28, 0x0C])
    code.extend([0xFE, 0x02])
    code.extend([0x38, 0x04])
    code.extend([0x1E, 0x07])
    code.extend([0x18, 0x06])
    code.extend([0x1E, 0x06])
    code.extend([0x18, 0x02])
    code.extend([0x1E, 0x00])

    table_low = tile_table_addr & 0xFF
    table_high = (tile_table_addr >> 8) & 0xFF

    # Process 0xFE00 only
    code.extend([0x21, 0x00, 0xFE])
    code.extend([0x06, 0x28])

    loop_start = len(code)

    code.extend([0x3E, 0x28])
    code.append(0x90)
    code.extend([0xFE, 0x04])
    code.extend([0x30, 0x03])

    code.append(0x7A)
    code.extend([0x18, 0x12])

    code.append(0x7B)
    code.append(0xB7)
    code.extend([0x20, 0x0E])

    code.append(0xE5)
    code.append(0x23)
    code.append(0x23)
    code.append(0x7E)
    code.extend([0xC6, table_low])
    code.append(0x6F)
    code.extend([0x3E, table_high])
    code.extend([0xCE, 0x00])
    code.append(0x67)
    code.append(0x7E)
    code.append(0xE1)

    code.append(0x4F)
    code.append(0x23)
    code.append(0x23)
    code.append(0x23)
    code.append(0x7E)
    code.extend([0xE6, 0xF8])
    code.append(0xB1)
    code.append(0x77)
    code.append(0x23)
    code.append(0x05)

    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_palette_loader(palette_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes with dynamic boss swap."""
    code = bytearray()

    # BG palettes
    code.extend([0x21, palette_addr & 0xFF, (palette_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])

    # OBJ palettes 0-5
    code.extend([0x3E, 0x80, 0xE0, 0x6A, 0x0E, 0x30])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Palette 6 (Gargoyle check)
    code.extend([0xF0, 0xBF, 0xFE, 0x01, 0x20, 0x05])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x18, 0x00])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Palette 7 (Spider check)
    obj_pal7 = palette_addr + 64 + 56
    code.extend([0x21, obj_pal7 & 0xFF, (obj_pal7 >> 8) & 0xFF])
    code.extend([0xF0, 0xBF, 0xFE, 0x02, 0x20, 0x05])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x18, 0x00])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.append(0xC9)
    return bytes(code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_v102.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    if not input_rom.exists():
        print(f"ERROR: Input ROM not found: {input_rom}")
        return

    rom = bytearray(input_rom.read_bytes())
    original_input = bytes(rom[0x0824:0x0824+46])

    rom, _ = apply_all_display_patches(rom)
    rom[0x143] = 0x80

    print(f"Loading palettes from: {palette_yaml}")
    bg_palettes, obj_palettes, gargoyle_pal, spider_pal = load_palettes_from_yaml(palette_yaml)

    print("\n=== v1.02: Post-Copy Palette Hook ===")
    print("  Strategy:")
    print("    1. Hook game's memcpy at 0x1F0C via trampoline at 0x0834")
    print("    2. After memcpy, colorize BOTH shadow buffers")
    print("    3. VBlank hook colorizes hardware OAM for immediate display")
    print("  This eliminates the race condition causing partial colorization.")
    print()

    BANK13_BASE = 0x034000

    PALETTE_DATA = 0x6800
    GARGOYLE_PAL = 0x6880
    SPIDER_PAL = 0x6888
    TILE_TABLE = 0x6890
    BUFFER_COLORIZER = 0x6990  # Called after memcpy
    VBLANK_COLORIZER = 0x6A80  # Called in VBlank
    PALETTE_LOADER = 0x6B00
    COMBINED_FUNC = 0x6B60

    # Post-copy trampoline at 0x0834 (in bank 0, after VBlank trampoline)
    POST_COPY_TRAMPOLINE = 0x0834

    # Write palette data
    offset = BANK13_BASE + (PALETTE_DATA - 0x4000)
    rom[offset:offset+64] = bg_palettes
    rom[offset+64:offset+128] = obj_palettes
    print(f"Palette data: 128 bytes at 0x{PALETTE_DATA:04X}")

    offset = BANK13_BASE + (GARGOYLE_PAL - 0x4000)
    rom[offset:offset+8] = gargoyle_pal
    offset = BANK13_BASE + (SPIDER_PAL - 0x4000)
    rom[offset:offset+8] = spider_pal

    tile_table = create_tile_palette_table()
    offset = BANK13_BASE + (TILE_TABLE - 0x4000)
    rom[offset:offset+256] = tile_table
    print(f"Tile table: 256 bytes at 0x{TILE_TABLE:04X}")

    # Buffer colorizer (called after memcpy)
    buffer_colorizer = create_buffer_colorizer(TILE_TABLE)
    offset = BANK13_BASE + (BUFFER_COLORIZER - 0x4000)
    rom[offset:offset+len(buffer_colorizer)] = buffer_colorizer
    print(f"Buffer colorizer: {len(buffer_colorizer)} bytes at 0x{BUFFER_COLORIZER:04X}")

    # VBlank colorizer (hardware OAM only)
    vblank_colorizer = create_vblank_oam_colorizer(TILE_TABLE)
    offset = BANK13_BASE + (VBLANK_COLORIZER - 0x4000)
    rom[offset:offset+len(vblank_colorizer)] = vblank_colorizer
    print(f"VBlank colorizer: {len(vblank_colorizer)} bytes at 0x{VBLANK_COLORIZER:04X}")

    # Palette loader
    palette_loader = create_palette_loader(PALETTE_DATA, GARGOYLE_PAL, SPIDER_PAL)
    offset = BANK13_BASE + (PALETTE_LOADER - 0x4000)
    rom[offset:offset+len(palette_loader)] = palette_loader
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{PALETTE_LOADER:04X}")

    # Combined function for VBlank
    combined = bytearray()
    combined.extend(original_input)
    if combined[-1] == 0xC9:
        combined = combined[:-1]
    combined.extend([0xCD, VBLANK_COLORIZER & 0xFF, VBLANK_COLORIZER >> 8])
    combined.extend([0xCD, PALETTE_LOADER & 0xFF, PALETTE_LOADER >> 8])
    combined.append(0xC9)

    offset = BANK13_BASE + (COMBINED_FUNC - 0x4000)
    rom[offset:offset+len(combined)] = combined
    print(f"Combined function: {len(combined)} bytes at 0x{COMBINED_FUNC:04X}")

    # VBlank trampoline at 0x0824
    vblank_trampoline = bytearray()
    vblank_trampoline.extend([0xF5])              # PUSH AF
    vblank_trampoline.extend([0x3E, 0x0D])        # LD A, 0x0D (bank 13)
    vblank_trampoline.extend([0xEA, 0x00, 0x20])  # LD (0x2000), A
    vblank_trampoline.extend([0xCD, COMBINED_FUNC & 0xFF, COMBINED_FUNC >> 8])
    vblank_trampoline.extend([0x3E, 0x01])        # LD A, 0x01 (bank 1)
    vblank_trampoline.extend([0xEA, 0x00, 0x20])  # LD (0x2000), A
    vblank_trampoline.extend([0xF1])              # POP AF
    vblank_trampoline.append(0xC9)                # RET

    rom[0x0824:0x0824+len(vblank_trampoline)] = vblank_trampoline
    print(f"VBlank trampoline: {len(vblank_trampoline)} bytes at 0x0824")

    # Post-copy trampoline at 0x0834
    # This replaces the CALL 0x09B3 (memcpy) at 0x1F0C
    post_copy = bytearray()
    post_copy.extend([0xCD, 0xB3, 0x09])         # CALL 0x09B3 (original memcpy)
    post_copy.extend([0xF5])                      # PUSH AF
    post_copy.extend([0x3E, 0x0D])                # LD A, 0x0D (bank 13)
    post_copy.extend([0xEA, 0x00, 0x20])          # LD (0x2000), A
    post_copy.extend([0xCD, BUFFER_COLORIZER & 0xFF, BUFFER_COLORIZER >> 8])
    post_copy.extend([0x3E, 0x01])                # LD A, 0x01 (bank 1)
    post_copy.extend([0xEA, 0x00, 0x20])          # LD (0x2000), A
    post_copy.extend([0xF1])                      # POP AF
    post_copy.append(0xC9)                        # RET

    rom[POST_COPY_TRAMPOLINE:POST_COPY_TRAMPOLINE+len(post_copy)] = post_copy
    print(f"Post-copy trampoline: {len(post_copy)} bytes at 0x{POST_COPY_TRAMPOLINE:04X}")

    # Fill remaining space with NOPs
    remaining_start = 0x0824 + len(vblank_trampoline)
    remaining_end = POST_COPY_TRAMPOLINE
    if remaining_end > remaining_start:
        rom[remaining_start:remaining_end] = bytes([0x00] * (remaining_end - remaining_start))

    remaining_start = POST_COPY_TRAMPOLINE + len(post_copy)
    remaining_end = 0x0852
    if remaining_end > remaining_start:
        rom[remaining_start:remaining_end] = bytes([0x00] * (remaining_end - remaining_start))

    # Patch ALL OAM copy calls to use our trampoline
    oam_copy_locations = [0x1F0C, 0x28E5, 0x36DE]
    print(f"\nPatching {len(oam_copy_locations)} OAM copy calls to use trampoline at 0x{POST_COPY_TRAMPOLINE:04X}:")
    for loc in oam_copy_locations:
        print(f"  0x{loc:04X}: CALL 0x09B3 -> CALL 0x{POST_COPY_TRAMPOLINE:04X}")
        rom[loc] = 0xCD
        rom[loc + 1] = POST_COPY_TRAMPOLINE & 0xFF
        rom[loc + 2] = (POST_COPY_TRAMPOLINE >> 8) & 0xFF

    # Fix checksum
    chk = 0
    for i in range(0x134, 0x14D):
        chk = (chk - rom[i] - 1) & 0xFF
    rom[0x14D] = chk

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nCreated: {output_rom}")
    print(f"Also: {fixed_rom}")


if __name__ == "__main__":
    main()
