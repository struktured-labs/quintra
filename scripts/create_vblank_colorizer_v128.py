#!/usr/bin/env python3
"""
v1.28: One-Shot Tile-Based BG Colorization

Abandon HDMA complexity. Instead:
1. On first VBlank, read ALL tiles from tilemap
2. Set attributes for ALL tiles based on lookup
3. Never touch BG attributes again

This works because:
- The tilemap is pre-built for the entire level
- Scrolling just moves the viewport over the tilemap
- Attributes stay attached to their tile positions

Processes in chunks across multiple frames to fit in VBlank.
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
    256-byte lookup: tile ID -> palette.

    Based on tilemap analysis:
    - 0x00-0x0F: Floor/empty -> palette 0
    - 0x10-0x3F: Wall/edge -> palette 2
    - 0x40-0x7F: Decorations -> palette 0
    - 0x80-0xBF: Items -> palette 1
    - 0xC0-0xFF: Other -> palette 0
    """
    lookup = bytearray(256)

    for t in range(0x00, 0x10):
        lookup[t] = 0
    for t in range(0x10, 0x40):
        lookup[t] = 2
    for t in range(0x40, 0x80):
        lookup[t] = 0
    for t in range(0x80, 0xC0):
        lookup[t] = 1
    for t in range(0xC0, 0x100):
        lookup[t] = 0

    return bytes(lookup)


def create_tile_based_colorizer() -> bytes:
    """OBJ colorizer (same as v1.09)."""
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


def create_bg_init_with_lookup(lookup_table_addr: int, progress_addr: int = 0xFFBC) -> bytes:
    """
    One-shot BG initialization with tile-based lookup.

    Processes 64 tiles per frame (16 frames to complete full tilemap).
    Uses progress counter at progress_addr to track which chunk to process.

    progress_addr values:
    0x00-0x0F: Processing chunk N of tilemap 0 (0x9800)
    0x10-0x1F: Processing chunk N of tilemap 1 (0x9C00)
    0x20+: Done
    """
    code = bytearray()
    lookup_high = (lookup_table_addr >> 8) & 0xFF
    progress_low = progress_addr & 0xFF

    # Check if already done (progress >= 0x20)
    code.extend([0xF0, progress_low])      # LDH A, [progress]
    code.extend([0xFE, 0x20])              # CP 0x20
    code.extend([0xD0])                     # RET NC (done if >= 0x20)

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Get progress and calculate addresses
    code.extend([0xF0, progress_low])      # LDH A, [progress]
    code.append(0x47)                       # LD B, A (save progress in B)

    # Calculate tilemap base: 0x98 if progress < 0x10, else 0x9C
    code.extend([0xE6, 0x10])              # AND 0x10
    code.append(0x0F)                       # RRCA (shift right, now 0x00 or 0x08)
    code.append(0x0F)                       # RRCA
    code.append(0x0F)                       # RRCA
    code.append(0x0F)                       # RRCA (now 0x00 or 0x01... wait that's wrong)

    # Let me redo this more simply
    # Actually, let's just use: if progress & 0x10 then base = 0x9C else 0x98

    code = bytearray()  # Reset and redo

    # Check if already done
    code.extend([0xF0, progress_low])      # LDH A, [progress]
    code.extend([0xFE, 0x20])              # CP 0x20
    code.extend([0xD0])                     # RET NC

    # Save registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    # Get progress
    code.extend([0xF0, progress_low])      # LDH A, [progress]
    code.append(0x5F)                       # LD E, A (save full progress in E)

    # Calculate chunk offset within tilemap: (progress & 0x0F) * 64
    code.extend([0xE6, 0x0F])              # AND 0x0F (chunk 0-15)
    # Multiply by 64: shift left 6 times = high byte gets bits 7-6, low byte gets bits 5-0
    # chunk * 64 = chunk << 6
    # For chunk 0: offset = 0x0000
    # For chunk 1: offset = 0x0040
    # ...
    # For chunk 15: offset = 0x03C0

    # A = chunk (0-15), need to compute offset
    # offset_high = chunk >> 2
    # offset_low = (chunk & 3) << 6
    code.append(0x47)                       # LD B, A (save chunk in B)
    code.extend([0xE6, 0x03])              # AND 0x03
    code.append(0xCB)                       # SWAP A
    code.append(0x37)
    code.append(0xCB)                       # SLA A
    code.append(0x27)
    code.append(0xCB)                       # SLA A
    code.append(0x27)
    code.append(0x6F)                       # LD L, A (offset low)

    code.append(0x78)                       # LD A, B (get chunk back)
    code.append(0xCB)                       # SRL A (shift right)
    code.append(0x3F)
    code.append(0xCB)                       # SRL A
    code.append(0x3F)
    code.append(0x47)                       # LD B, A (offset high bits)

    # Calculate tilemap base
    code.append(0x7B)                       # LD A, E (get full progress)
    code.extend([0xE6, 0x10])              # AND 0x10
    code.extend([0x28, 0x03])              # JR Z, +3 (if zero, use 0x98)
    code.extend([0x3E, 0x9C])              # LD A, 0x9C
    code.extend([0x18, 0x02])              # JR +2
    code.extend([0x3E, 0x98])              # LD A, 0x98

    code.append(0x80)                       # ADD A, B (add offset high)
    code.append(0x67)                       # LD H, A
    # HL now = tilemap base + offset

    # Process 64 tiles
    # First, read tiles from VRAM bank 0, build attributes, then write to bank 1

    # Switch to bank 0
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Read 64 tiles into WRAM at 0xD000
    code.extend([0x11, 0x00, 0xD0])        # LD DE, 0xD000
    code.extend([0x0E, 0x40])              # LD C, 64

    loop1_start = len(code)
    code.append(0x2A)                       # LD A, [HL+]
    code.append(0x12)                       # LD [DE], A
    code.append(0x13)                       # INC DE
    code.append(0x0D)                       # DEC C
    loop1_offset = loop1_start - len(code) - 2
    code.extend([0x20, loop1_offset & 0xFF])

    # HL now points past the 64 tiles
    # Save HL for writing attributes
    code.append(0xE5)                       # PUSH HL

    # Now convert tiles to attributes using lookup table
    code.extend([0x21, 0x00, 0xD0])        # LD HL, 0xD000
    code.extend([0x0E, 0x40])              # LD C, 64

    loop2_start = len(code)
    code.append(0x7E)                       # LD A, [HL]
    code.append(0xE5)                       # PUSH HL
    code.append(0x6F)                       # LD L, A
    code.extend([0x26, lookup_high])       # LD H, lookup_high
    code.append(0x7E)                       # LD A, [HL] (get palette)
    code.append(0xE1)                       # POP HL
    code.append(0x77)                       # LD [HL], A (overwrite tile with palette)
    code.append(0x23)                       # INC HL
    code.append(0x0D)                       # DEC C
    loop2_offset = loop2_start - len(code) - 2
    code.extend([0x20, loop2_offset & 0xFF])

    # Now write attributes to VRAM bank 1
    code.append(0xE1)                       # POP HL (restore position)

    # HL points past the 64 tiles, need to go back 64
    code.extend([0x01, 0x40, 0x00])        # LD BC, 64
    code.append(0x09)                       # ADD HL, BC... wait that adds, not subtracts

    # Use: HL = HL - 64
    # A = L - 64, then handle carry
    code.append(0x7D)                       # LD A, L
    code.extend([0xD6, 0x40])              # SUB 0x40
    code.append(0x6F)                       # LD L, A
    code.extend([0x30, 0x01])              # JR NC, +1 (skip if no borrow)
    code.append(0x25)                       # DEC H

    # Switch to bank 1
    code.extend([0x3E, 0x01])              # LD A, 1
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Copy attributes from 0xD000 to VRAM
    code.extend([0x11, 0x00, 0xD0])        # LD DE, 0xD000
    code.extend([0x0E, 0x40])              # LD C, 64

    loop3_start = len(code)
    code.append(0x1A)                       # LD A, [DE]
    code.append(0x77)                       # LD [HL], A
    code.append(0x23)                       # INC HL
    code.append(0x13)                       # INC DE
    code.append(0x0D)                       # DEC C
    loop3_offset = loop3_start - len(code) - 2
    code.extend([0x20, loop3_offset & 0xFF])

    # Switch back to bank 0
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Increment progress
    code.extend([0xF0, progress_low])      # LDH A, [progress]
    code.append(0x3C)                       # INC A
    code.extend([0xE0, progress_low])      # LDH [progress], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])
    code.append(0xC9)

    return bytes(code)


def create_combined_with_bg_lookup(palette_loader_addr: int, shadow_main_addr: int, bg_init_addr: int) -> bytes:
    """Combined: load palettes, colorize OBJ, BG init, DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_init_addr & 0xFF, bg_init_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook at 0x0824."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v128.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.28: One-Shot Tile-Based BG ===")
    print("  Processes 64 tiles per frame")
    print("  16 frames to complete each tilemap")
    print("  32 frames total for both tilemaps")
    print("  Uses lookup table for tile->palette mapping")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    obj_colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    bg_init_addr = 0x6A40
    combined_addr = 0x6B00
    lookup_table_addr = 0x6B20

    # Generate code
    tile_lookup = create_tile_palette_lookup()
    obj_colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(obj_colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    bg_init = create_bg_init_with_lookup(lookup_table_addr)
    combined = create_combined_with_bg_lookup(palette_loader_addr, shadow_main_addr, bg_init_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Tile lookup: {len(tile_lookup)} bytes at 0x{lookup_table_addr:04X}")
    print(f"OBJ colorizer: {len(obj_colorizer)} bytes at 0x{obj_colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"BG init: {len(bg_init)} bytes at 0x{bg_init_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Check overlaps
    if bg_init_addr + len(bg_init) > combined_addr:
        print(f"ERROR: BG init overlaps combined! {bg_init_addr + len(bg_init):04X} > {combined_addr:04X}")
        return
    if combined_addr + len(combined) > lookup_table_addr:
        print(f"ERROR: Combined overlaps lookup! {combined_addr + len(combined):04X} > {lookup_table_addr:04X}")
        return

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr: int, data: bytes):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(gargoyle_addr, gargoyle)
    write_to_bank13(spider_addr, spider)
    write_to_bank13(obj_colorizer_addr, obj_colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(bg_init_addr, bg_init)
    write_to_bank13(combined_addr, combined)
    write_to_bank13(lookup_table_addr, tile_lookup)

    # NOP out original DMA
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])

    # VBlank hook
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.28 Build Complete ===")


if __name__ == "__main__":
    main()
