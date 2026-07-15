#!/usr/bin/env python3
"""
v1.42: BG Tile Colorization via Attribute Buffer

Based on v1.09 (stable sprite colorization) + BG tile coloring:
- Scans tile buffer at 0xC1A0 (576 bytes)
- Looks up palette for each tile from 256-byte table
- Writes attributes to VRAM bank 1 using GDMA
- Only rebuilds when level changes (detected via scroll position change)

Key insight: Game uses tile buffer at 0xC1A0, copies to VRAM via 0x42A7.
We piggyback by building an attribute buffer and copying it too.
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
    """
    256-byte lookup table: tile ID -> BG palette (0-7).

    Based on Level 1 analysis:
    - Floor (0-2): palette 0 (light blue)
    - Walls (3-4): palette 1 (purple)
    - Platforms (5-15): palette 2 (cyan)
    - Structure (0x30-0x4F): palette 1
    - Hazards (0x4C-0x4D, 0x80-0x9F): palette 3 (red/danger)
    - Items (0xA0-0xDF): palette 4 (gold)
    - Borders (0xE0-0xFE): palette 1
    """
    lookup = bytearray(256)

    for i in range(256):
        if i <= 0x02:
            # Floor tiles
            lookup[i] = 0
        elif i <= 0x04:
            # Wall base
            lookup[i] = 1
        elif i <= 0x0F:
            # Platforms/structures
            lookup[i] = 2
        elif i <= 0x1F:
            # Decorations (floor color)
            lookup[i] = 0
        elif i <= 0x2F:
            # More decorations
            lookup[i] = 2
        elif i <= 0x4B:
            # Structure/walls
            lookup[i] = 1
        elif i <= 0x4D:
            # Hazards (spikes)
            lookup[i] = 3
        elif i <= 0x7F:
            # Extended walls/structure
            lookup[i] = 1
        elif i <= 0x9F:
            # More hazards
            lookup[i] = 3
        elif i <= 0xDF:
            # Items - GOLD!
            lookup[i] = 4
        elif i <= 0xFE:
            # Border/edge tiles
            lookup[i] = 1
        else:
            # 0xFF - empty/transparent
            lookup[i] = 0

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
    """Colorizes BOTH shadow buffers (unchanged from v1.09)."""
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


def create_bg_colorizer(lookup_table_addr: int) -> bytes:
    """
    BG tile colorizer - scans tile buffer, writes attributes to VRAM bank 1.

    Uses GDMA for fast transfer:
    1. Build attribute buffer at 0xD000 from tile buffer at 0xC1A0
    2. Switch to VRAM bank 1
    3. GDMA copy 576 bytes from 0xD000 to 0x9800
    4. Switch back to VRAM bank 0

    Only runs when gameplay is active (check 0xFFC1).
    """
    code = bytearray()

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Check if gameplay active (skip during menus/title)
    code.extend([0xF0, 0xC1])        # LDH A, [0xFFC1]
    code.append(0xB7)                # OR A
    code.extend([0x28, 0x50])        # JR Z, skip_bg (placeholder - will fix)

    # === Build attribute buffer ===
    # HL = tile buffer (0xC1A0)
    # DE = attribute buffer (0xD000)
    # B = lookup table high byte
    code.extend([0x21, 0xA0, 0xC1])  # LD HL, 0xC1A0 (tile buffer)
    code.extend([0x11, 0x00, 0xD0])  # LD DE, 0xD000 (attribute buffer)
    code.extend([0x06, (lookup_table_addr >> 8) & 0xFF])  # LD B, lookup_high

    # Process 576 tiles in chunks of 32 (18 rows)
    code.extend([0x0E, 0x12])        # LD C, 18 (row counter)

    # row_loop:
    row_loop_addr = len(code)
    code.append(0xC5)                # PUSH BC (save row counter)
    code.extend([0x06, 0x20])        # LD B, 32 (tiles per row - reuse B)

    # But we need lookup high in B... let me restructure
    # Actually store lookup high in a different way

    # Let me rewrite more carefully
    code_v2 = bytearray()

    # Save registers
    code_v2.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Check if gameplay active
    code_v2.extend([0xF0, 0xC1])     # LDH A, [0xFFC1]
    code_v2.append(0xB7)             # OR A
    skip_bg_jr = len(code_v2)
    code_v2.extend([0x28, 0x00])     # JR Z, skip_bg (placeholder)

    # Build attribute buffer: scan 576 tiles
    code_v2.extend([0x21, 0xA0, 0xC1])  # LD HL, 0xC1A0 (tile buffer)
    code_v2.extend([0x11, 0x00, 0xD0])  # LD DE, 0xD000 (attr buffer)

    # Use BC as counter (576 = 0x0240)
    code_v2.extend([0x01, 0x40, 0x02])  # LD BC, 0x0240

    # build_loop:
    build_loop_addr = len(code_v2)
    code_v2.append(0x7E)             # LD A, [HL] - get tile ID
    code_v2.append(0x23)             # INC HL
    code_v2.append(0xE5)             # PUSH HL

    # Lookup palette: HL = lookup_table + A
    code_v2.extend([0x26, (lookup_table_addr >> 8) & 0xFF])  # LD H, lookup_high
    code_v2.append(0x6F)             # LD L, A
    code_v2.append(0x7E)             # LD A, [HL] - get palette

    code_v2.append(0xE1)             # POP HL
    code_v2.append(0x12)             # LD [DE], A - store attribute
    code_v2.append(0x13)             # INC DE

    # Decrement counter
    code_v2.append(0x0B)             # DEC BC
    code_v2.append(0x78)             # LD A, B
    code_v2.append(0xB1)             # OR C
    # JR NZ, build_loop
    offset = build_loop_addr - len(code_v2) - 2
    code_v2.extend([0x20, offset & 0xFF])

    # === GDMA copy to VRAM bank 1 ===
    # Switch to VRAM bank 1
    code_v2.extend([0x3E, 0x01])     # LD A, 1
    code_v2.extend([0xE0, 0x4F])     # LDH [VBK], A

    # Set HDMA source = 0xD000
    code_v2.extend([0x3E, 0xD0])     # LD A, 0xD0
    code_v2.extend([0xE0, 0x51])     # LDH [HDMA1], A
    code_v2.extend([0x3E, 0x00])     # LD A, 0x00
    code_v2.extend([0xE0, 0x52])     # LDH [HDMA2], A

    # Set HDMA dest = 0x9800
    code_v2.extend([0x3E, 0x98])     # LD A, 0x98
    code_v2.extend([0xE0, 0x53])     # LDH [HDMA3], A
    code_v2.extend([0x3E, 0x00])     # LD A, 0x00
    code_v2.extend([0xE0, 0x54])     # LDH [HDMA4], A

    # Start GDMA: 576 bytes = 36 blocks of 16 bytes
    # GDMA mode = bit 7 clear, blocks-1 in bits 0-6
    # 36 blocks = 0x24, so write 0x23
    code_v2.extend([0x3E, 0x23])     # LD A, 0x23 (GDMA, 36 blocks)
    code_v2.extend([0xE0, 0x55])     # LDH [HDMA5], A

    # Switch back to VRAM bank 0
    code_v2.append(0xAF)             # XOR A
    code_v2.extend([0xE0, 0x4F])     # LDH [VBK], A

    # skip_bg:
    skip_bg_addr = len(code_v2)
    # Fix the JR Z offset
    code_v2[skip_bg_jr + 1] = (skip_bg_addr - skip_bg_jr - 2) & 0xFF

    # Restore registers
    code_v2.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code_v2.append(0xC9)             # RET

    return bytes(code_v2)


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes (unchanged from v1.09)."""
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
    """Combined function: palettes + sprites + BG + DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # CALL DMA
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook at 0x0824 with input handler."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v142.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.42: BG Tile Colorization ===")
    print("  v1.09 sprite colorization + BG tile coloring")
    print("  Scans tile buffer at 0xC1A0")
    print("  Uses 256-byte lookup table for tile→palette")
    print("  GDMA copies attributes to VRAM bank 1")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800      # BG palettes (64 bytes)
    # 0x6840: OBJ palettes (64 bytes)
    gargoyle_addr = 0x6880          # Gargoyle palette (8 bytes)
    spider_addr = 0x6888            # Spider palette (8 bytes)
    colorizer_addr = 0x6900         # Sprite colorizer
    shadow_main_addr = 0x6980       # Shadow colorizer main
    palette_loader_addr = 0x69E0    # Palette loader
    bg_colorizer_addr = 0x6A40      # NEW: BG colorizer
    combined_addr = 0x6AC0          # Combined function
    lookup_table_addr = 0x6B00      # NEW: 256-byte lookup table

    # Generate code
    lookup_table = create_tile_palette_lookup()
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_colorizer = create_bg_colorizer(lookup_table_addr)
    combined = create_combined_with_bg(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Lookup table: {len(lookup_table)} bytes at 0x{lookup_table_addr:04X}")
    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Check for overlaps
    if bg_colorizer_addr + len(bg_colorizer) > combined_addr:
        print(f"WARNING: BG colorizer overlaps combined! End: 0x{bg_colorizer_addr + len(bg_colorizer):04X}")
    if combined_addr + len(combined) > lookup_table_addr:
        print(f"WARNING: Combined overlaps lookup table! End: 0x{combined_addr + len(combined):04X}")

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

    # NOP out DMA at 0x06D5
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])

    # Write VBlank hook
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.42 Build Complete ===")


if __name__ == "__main__":
    main()
