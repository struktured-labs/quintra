#!/usr/bin/env python3
"""
v0.98: BG attribute modification for item/wall coloring.

Features:
- All v0.97 sprite colorization (Sara W/D, boss palettes, tile-based enemies)
- BG palette 0: Floor tiles (blue castle)
- BG palette 1: Items/pickups (gold/yellow)
- BG palette 2: Walls/void (darker slate)
- BG attribute modifier colors tiles based on tile ID
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def create_tile_palette_table() -> bytes:
    """Create 256-byte tile-to-palette lookup table for sprites (normal mode)."""
    table = bytearray(256)

    for tile in range(256):
        if tile < 0x20:
            table[tile] = 0  # Effects
        elif tile < 0x28:
            table[tile] = 2  # Sara W
        elif tile < 0x30:
            table[tile] = 1  # Sara D
        elif tile < 0x40:
            table[tile] = 3  # Crow/flying dark
        elif tile < 0x50:
            table[tile] = 4  # Hornets/flying
        elif tile < 0x60:
            table[tile] = 4  # Ground/orc
        elif tile < 0x70:
            table[tile] = 5  # Humanoid
        elif tile < 0x80:
            table[tile] = 3  # Catfish/special
        else:
            table[tile] = 4  # Default

    return bytes(table)


def create_bg_tile_palette_table() -> bytes:
    """
    Create 256-byte BG tile-to-palette lookup table.

    Based on tile analysis:
    - Tile 254: Void/walls -> Palette 2 (darker slate)
    - Tiles 165, 185, 192, 195, 207, 240, 243, 252: Items -> Palette 1 (gold)
    - Other high tiles (>150): Likely items -> Palette 1
    - Normal tiles (0-150): Floor -> Palette 0 (blue)
    """
    table = bytearray(256)

    # Default all to palette 0 (main floor blue)
    for i in range(256):
        table[i] = 0

    # Item tiles get palette 1 (gold) - high tiles are typically items
    item_tiles = [165, 185, 192, 195, 207, 240, 243, 252]
    for tile in item_tiles:
        table[tile] = 1

    # Also mark tiles 150-250 as potential items (except 254)
    for tile in range(150, 254):
        table[tile] = 1

    # Wall/void tiles get palette 2 (darker slate)
    table[254] = 2
    table[255] = 2

    return bytes(table)


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes]:
    """Load BG and OBJ palettes from YAML file."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors: list[str]) -> bytes:
        result = bytearray()
        for c in colors:
            val = int(c, 16) & 0x7FFF
            result.extend([val & 0xFF, (val >> 8) & 0xFF])
        return bytes(result)

    # BG palettes
    bg_keys = ['Dungeon', 'BG1', 'BG2', 'BG3', 'BG4', 'BG5', 'BG6', 'BG7']
    bg_data = bytearray()
    for key in bg_keys:
        if key in data.get('bg_palettes', {}):
            bg_data.extend(pal_to_bytes(data['bg_palettes'][key]['colors']))
        else:
            bg_data.extend(pal_to_bytes(["7FFF", "5294", "2108", "0000"]))

    # OBJ palettes
    obj_keys = ['Effects', 'SaraDragon', 'SaraWitch', 'CrowCatfish',
                'ItemsGold', 'HumanoidPurple', 'GargoyleBoss', 'SpiderBoss']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

    return bytes(bg_data), bytes(obj_data)


def create_v097_oam_loop(tile_table_addr: int) -> bytes:
    """v0.97 OAM colorization loop (same as before)."""
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # === Determine Sara palette (store in D) ===
    code.extend([0xF0, 0xBE])        # LDH A, [0xFFBE] - Sara form flag
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x04])        # JR NZ, +4 (Sara D)
    code.extend([0x16, 0x02])        # LD D, 2 (Sara W)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x16, 0x01])        # LD D, 1 (Sara D)

    # === Determine enemy palette (store in E) ===
    code.extend([0xF0, 0xBF])        # LDH A, [0xFFBF]
    code.append(0xB7)                # OR A
    code.extend([0x28, 0x0C])        # JR Z, +12 (no boss)

    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x38, 0x04])        # JR C, +4 (Gargoyle)
    code.extend([0x1E, 0x07])        # LD E, 7 (Spider)
    code.extend([0x18, 0x06])        # JR +6
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x1E, 0x00])        # LD E, 0

    table_low = tile_table_addr & 0xFF
    table_high = (tile_table_addr >> 8) & 0xFF

    for base_hi in [0xFE, 0xC0, 0xC1]:
        code.extend([0x21, 0x00, base_hi])  # LD HL, base
        code.extend([0x06, 0x28])           # LD B, 40

        loop_start = len(code)

        code.extend([0x3E, 0x28])    # LD A, 40
        code.append(0x90)            # SUB B
        code.extend([0xFE, 0x04])    # CP 4
        code.extend([0x30, 0x03])    # JR NC, +3

        code.append(0x7A)            # LD A, D (Sara)
        code.extend([0x18, 0x12])    # JR +18

        code.append(0x7B)            # LD A, E
        code.append(0xB7)            # OR A
        code.extend([0x20, 0x0E])    # JR NZ, +14 (boss palette)

        code.append(0xE5)            # PUSH HL
        code.append(0x23)            # INC HL
        code.append(0x23)            # INC HL
        code.append(0x7E)            # LD A, [HL]
        code.extend([0xC6, table_low])  # ADD A, low
        code.append(0x6F)            # LD L, A
        code.extend([0x3E, table_high])  # LD A, high
        code.extend([0xCE, 0x00])    # ADC A, 0
        code.append(0x67)            # LD H, A
        code.append(0x7E)            # LD A, [HL]
        code.append(0xE1)            # POP HL

        code.append(0x4F)            # LD C, A
        code.append(0x23)            # INC HL
        code.append(0x23)            # INC HL
        code.append(0x23)            # INC HL
        code.append(0x7E)            # LD A, [HL]
        code.extend([0xE6, 0xF8])    # AND 0xF8
        code.append(0xB1)            # OR C
        code.append(0x77)            # LD [HL], A

        code.append(0x23)            # INC HL
        code.append(0x05)            # DEC B

        loop_offset = loop_start - len(code) - 2
        code.extend([0x20, loop_offset & 0xFF])

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)  # RET

    return bytes(code)


def create_bg_attr_modifier(bg_table_addr: int) -> bytes:
    """
    Create BG attribute modifier loop.

    Scans visible BG tiles and sets palette based on tile ID:
    - Reads tile from bank 0 (0x9800)
    - Looks up palette in table
    - Writes attribute to bank 1 (0x9800)

    For efficiency, only processes 128 tiles per call (top half of screen).
    Next call processes bottom half. This spreads work across frames.

    Uses toggle at 0xFF8F to alternate halves.
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Get scroll position to determine which part of tile map is visible
    # For simplicity, process a fixed 256 bytes of the tile map (8 rows)
    # Toggle between rows 0-7 and 8-15 using 0xFF8F

    code.extend([0xF0, 0x8F])        # LDH A, [0xFF8F] - toggle
    code.append(0xEE)                # XOR
    code.append(0x01)                # 0x01 - flip bit
    code.extend([0xE0, 0x8F])        # LDH [0xFF8F], A
    code.append(0xB7)                # OR A (test)
    code.extend([0x28, 0x04])        # JR Z, +4 (process rows 0-7)
    code.extend([0x0E, 0x00])        # LD C, 0x00 (rows 8-15: start at 0x9900)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x0E, 0x00])        # LD C, 0x00 (rows 0-7: start at 0x9800)
    # Note: We'll use starting address 0x9800 for rows 0-7, 0x9900 for rows 8-15

    # Actually, let's simplify - just process 256 tiles from 0x9800
    # This covers most of the visible area

    # Set VRAM bank to 0 (read tiles)
    code.extend([0x3E, 0x00])        # LD A, 0
    code.extend([0xE0, 0x4F])        # LDH [0xFF4F], A (VBK)

    # HL = tile map (0x9800), DE = we'll use for attr write
    code.extend([0x21, 0x00, 0x98])  # LD HL, 0x9800
    code.extend([0x11, 0x00, 0x98])  # LD DE, 0x9800 (attr map same addr in bank 1)
    code.extend([0x06, 0x00])        # LD B, 0 (256 iterations, 0 means 256)

    table_low = bg_table_addr & 0xFF   # 0x00
    table_high = (bg_table_addr >> 8) & 0xFF  # 0x69

    loop_start = len(code)

    # Read tile ID from bank 0
    code.append(0x7E)                # LD A, [HL]
    code.append(0xE5)                # PUSH HL (save position)

    # Look up palette in table (HL = 0x6900 + A)
    code.extend([0xC6, table_low])   # ADD A, table_low
    code.append(0x6F)                # LD L, A
    code.extend([0x3E, table_high])  # LD A, table_high
    code.extend([0xCE, 0x00])        # ADC A, 0
    code.append(0x67)                # LD H, A
    code.append(0x4E)                # LD C, [HL] - palette number

    code.append(0xE1)                # POP HL (restore position)

    # Switch to VRAM bank 1 to write attribute
    code.append(0xD5)                # PUSH DE
    code.extend([0x3E, 0x01])        # LD A, 1
    code.extend([0xE0, 0x4F])        # LDH [0xFF4F], A (VBK=1)

    # Write attribute (palette in C, other bits 0)
    # DE has same address as HL, write palette there
    code.append(0xD1)                # POP DE
    code.append(0x79)                # LD A, C
    code.append(0x12)                # LD [DE], A

    # Switch back to VRAM bank 0
    code.extend([0x3E, 0x00])        # LD A, 0
    code.extend([0xE0, 0x4F])        # LDH [0xFF4F], A (VBK=0)

    # Next position
    code.append(0x23)                # INC HL
    code.append(0x13)                # INC DE
    code.append(0x05)                # DEC B

    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])  # JR NZ, loop

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)  # RET

    return bytes(code)


def create_palette_loader() -> bytes:
    """Load CGB palettes from bank 13 data at 0x6800."""
    code = bytearray()

    # BG palettes (at 0x6800)
    code.extend([
        0x21, 0x00, 0x68,  # LD HL, 0x6800
        0x3E, 0x80,        # LD A, 0x80 (auto-increment)
        0xE0, 0x68,        # LDH [0x68], A (BGPI)
        0x0E, 0x40,        # LD C, 64
    ])
    code.extend([
        0x2A,              # LD A, [HL+]
        0xE0, 0x69,        # LDH [0x69], A (BGPD)
        0x0D,              # DEC C
        0x20, 0xFA,        # JR NZ, -6
    ])

    # OBJ palettes
    code.extend([
        0x3E, 0x80,        # LD A, 0x80
        0xE0, 0x6A,        # LDH [0x6A], A (OBPI)
        0x0E, 0x40,        # LD C, 64
    ])
    code.extend([
        0x2A,              # LD A, [HL+]
        0xE0, 0x6B,        # LDH [0x6B], A (OBPD)
        0x0D,              # DEC C
        0x20, 0xFA,        # JR NZ, -6
    ])

    code.append(0xC9)  # RET
    return bytes(code)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_v098.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    if not input_rom.exists():
        print(f"ERROR: Input ROM not found: {input_rom}")
        return

    if not palette_yaml.exists():
        print(f"ERROR: Palette file not found: {palette_yaml}")
        return

    rom = bytearray(input_rom.read_bytes())

    # Save original input handler BEFORE any patches
    original_input = bytes(rom[0x0824:0x0824+46])

    rom, _ = apply_all_display_patches(rom)
    rom[0x143] = 0x80  # CGB flag

    # Load palettes
    print(f"Loading palettes from: {palette_yaml}")
    bg_palettes, obj_palettes = load_palettes_from_yaml(palette_yaml)

    print("\n=== v0.98: BG attribute coloring ===")
    print("  BG Palette 0: Floor (blue castle)")
    print("  BG Palette 1: Items (gold)")
    print("  BG Palette 2: Walls/void (slate)")
    print("  + All v0.97 sprite colorization")
    print()

    BANK13_BASE = 0x034000  # Bank 13 file offset

    # === BANK 13 LAYOUT (v0.98) ===
    PALETTE_DATA = 0x6800      # 128 bytes
    SPRITE_TILE_TABLE = 0x6880 # 256 bytes (sprite colorization)
    BG_TILE_TABLE = 0x6980     # 256 bytes (BG colorization) - NEW
    OAM_LOOP = 0x6A80          # ~200 bytes
    BG_ATTR_LOOP = 0x6B60      # ~80 bytes - NEW
    PALETTE_LOADER = 0x6BC0    # ~40 bytes
    COMBINED_FUNC = 0x6BF0     # ~70 bytes

    # Write palette data
    offset = BANK13_BASE + (PALETTE_DATA - 0x4000)
    rom[offset:offset+64] = bg_palettes
    rom[offset+64:offset+128] = obj_palettes
    print(f"Palette data: 128 bytes at 0x{PALETTE_DATA:04X}")

    # Write sprite tile lookup table
    sprite_table = create_tile_palette_table()
    offset = BANK13_BASE + (SPRITE_TILE_TABLE - 0x4000)
    rom[offset:offset+256] = sprite_table
    print(f"Sprite tile table: 256 bytes at 0x{SPRITE_TILE_TABLE:04X}")

    # Write BG tile lookup table - NEW
    bg_table = create_bg_tile_palette_table()
    offset = BANK13_BASE + (BG_TILE_TABLE - 0x4000)
    rom[offset:offset+256] = bg_table
    print(f"BG tile table: 256 bytes at 0x{BG_TILE_TABLE:04X}")

    # Write OAM loop
    oam_loop = create_v097_oam_loop(SPRITE_TILE_TABLE)
    offset = BANK13_BASE + (OAM_LOOP - 0x4000)
    rom[offset:offset+len(oam_loop)] = oam_loop
    print(f"OAM loop: {len(oam_loop)} bytes at 0x{OAM_LOOP:04X}")

    # Write BG attribute loop - NEW
    bg_attr_loop = create_bg_attr_modifier(BG_TILE_TABLE)
    offset = BANK13_BASE + (BG_ATTR_LOOP - 0x4000)
    rom[offset:offset+len(bg_attr_loop)] = bg_attr_loop
    print(f"BG attr loop: {len(bg_attr_loop)} bytes at 0x{BG_ATTR_LOOP:04X}")

    # Write palette loader
    palette_loader = create_palette_loader()
    offset = BANK13_BASE + (PALETTE_LOADER - 0x4000)
    rom[offset:offset+len(palette_loader)] = palette_loader
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{PALETTE_LOADER:04X}")

    # Write combined function: original input + OAM loop + BG attr loop + palette loader
    combined = bytearray()
    combined.extend(original_input)
    if combined[-1] == 0xC9:
        combined = combined[:-1]
    combined.extend([0xCD, OAM_LOOP & 0xFF, OAM_LOOP >> 8])
    combined.extend([0xCD, BG_ATTR_LOOP & 0xFF, BG_ATTR_LOOP >> 8])
    combined.extend([0xCD, PALETTE_LOADER & 0xFF, PALETTE_LOADER >> 8])
    combined.append(0xC9)

    offset = BANK13_BASE + (COMBINED_FUNC - 0x4000)
    rom[offset:offset+len(combined)] = combined
    print(f"Combined function: {len(combined)} bytes at 0x{COMBINED_FUNC:04X}")

    # === TRAMPOLINE ===
    trampoline = bytearray()
    trampoline.extend([0xF5])  # PUSH AF
    trampoline.extend([0x3E, 0x0D])  # LD A, 13
    trampoline.extend([0xEA, 0x00, 0x20])  # LD [0x2000], A
    trampoline.extend([0xCD, COMBINED_FUNC & 0xFF, COMBINED_FUNC >> 8])
    trampoline.extend([0x3E, 0x01])  # LD A, 1
    trampoline.extend([0xEA, 0x00, 0x20])  # LD [0x2000], A
    trampoline.extend([0xF1])  # POP AF
    trampoline.append(0xC9)  # RET

    rom[0x0824:0x0824+len(trampoline)] = trampoline
    remaining = 46 - len(trampoline)
    if remaining > 0:
        rom[0x0824+len(trampoline):0x0824+46] = bytes([0x00] * remaining)
    print(f"Trampoline: {len(trampoline)} bytes at 0x0824")

    # Fix header checksum
    chk = 0
    for i in range(0x134, 0x14D):
        chk = (chk - rom[i] - 1) & 0xFF
    rom[0x14D] = chk

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    output_rom.write_bytes(rom)

    # Also copy to FIXED for testing
    fixed_rom.write_bytes(rom)

    print(f"\nCreated: {output_rom}")
    print(f"Also: {fixed_rom}")
    print("  v0.98: BG attribute coloring + sprite colorization")


if __name__ == "__main__":
    main()
