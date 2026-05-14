#!/usr/bin/env python3
"""
v1.26: HDMA-Based BG Colorization

The problem with all previous approaches:
- v1.21: VBlank scanning 4 rows/frame - too slow, flickering
- v1.23: Hook tile copy at 0x4295 - bank switching conflicts
- v1.24: Position-based attributes - don't scroll with tilemap
- v1.25: Uniform palette - works but boring

Solution: Use GBC HDMA hardware to stream attributes from WRAM to VRAM.

Architecture:
- Lookup table in ROM at 0x6B00 (256 bytes): tile ID -> palette
- WRAM buffer at 0xD000 (256 bytes): computed attributes
- Per frame: read 256 tiles, lookup palettes, HDMA to VRAM bank 1
- 4 batches cover entire tilemap (1024 bytes) every 4 frames

HDMA Registers:
- FF51/FF52: Source address (WRAM buffer)
- FF53/FF54: Destination address (VRAM bank 1)
- FF55: Control - bit 7=HBlank mode, bits 0-6=length-1
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
    Create 256-byte lookup table: tile ID -> BG palette.

    Based on observed BG tile patterns:
    - 0x00-0x3F: Floor/background tiles -> palette 0 (dungeon main)
    - 0x40-0x7F: Wall/structure tiles -> palette 2 (purple/blue walls)
    - 0x80-0x9F: Hazard tiles -> palette 3 (green/danger)
    - 0xA0-0xDF: Item/special tiles -> palette 1 (gold/items)
    - 0xE0-0xFF: Decoration -> palette 0
    """
    lookup = bytearray(256)

    # Floor/background (palette 0)
    for t in range(0x00, 0x40):
        lookup[t] = 0

    # Walls (palette 2 - purple/blue)
    for t in range(0x40, 0x80):
        lookup[t] = 2

    # Hazards (palette 3 - green/danger)
    for t in range(0x80, 0xA0):
        lookup[t] = 3

    # Items (palette 1 - gold)
    for t in range(0xA0, 0xE0):
        lookup[t] = 1

    # Decoration (palette 0)
    for t in range(0xE0, 0x100):
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


def create_hdma_bg_colorizer(lookup_table_addr: int) -> bytes:
    """
    HDMA-based BG colorizer.

    Processes 256 tiles per frame in 4 batches (full tilemap every 4 frames).

    Per frame:
    1. Read batch counter (0-3) from 0xFFBC
    2. Calculate VRAM source: 0x9800 + batch*256
    3. Read 256 tiles from VRAM bank 0
    4. For each tile, lookup palette from ROM table
    5. Store palette in WRAM buffer at 0xD000
    6. Configure HDMA: source=0xD000, dest=VRAM bank 1 at same offset
    7. Start HBlank DMA (16 bytes per HBlank, 256 bytes = 16 transfers)
    8. Increment batch counter

    Registers used:
    - HL: VRAM source pointer
    - DE: WRAM dest pointer
    - BC: loop counter
    - 0xFFBC: batch counter (0-3)
    - 0xFFBE: temp storage for VRAM high byte
    """
    code = bytearray()
    lookup_high = (lookup_table_addr >> 8) & 0xFF

    # Save all registers
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Get batch counter (0-3)
    code.extend([0xF0, 0xBC])              # LDH A, [0xFFBC]
    code.extend([0xE6, 0x03])              # AND 0x03

    # Calculate VRAM source high byte: 0x98 + batch
    code.extend([0xC6, 0x98])              # ADD A, 0x98
    code.extend([0xE0, 0xBE])              # LDH [0xFFBE], A (save for HDMA dest)
    code.append(0x67)                       # LD H, A
    code.extend([0x2E, 0x00])              # LD L, 0

    # Switch to VRAM bank 0 for reading tile IDs
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # DE = WRAM buffer at 0xD000
    code.extend([0x11, 0x00, 0xD0])        # LD DE, 0xD000

    # BC = 256 (0x0100) - loop counter
    code.extend([0x01, 0x00, 0x01])        # LD BC, 0x0100

    # ===== Build loop: read tile, lookup palette, store in buffer =====
    loop_start = len(code)

    # Read tile ID from VRAM
    code.append(0x2A)                       # LD A, [HL+]  (2 cycles)

    # Lookup palette from ROM table
    # Save HL, set HL = lookup_table + tile_id, read, restore HL
    code.append(0xE5)                       # PUSH HL      (4 cycles)
    code.append(0x6F)                       # LD L, A      (1 cycle)
    code.extend([0x26, lookup_high])       # LD H, high   (2 cycles)
    code.append(0x7E)                       # LD A, [HL]   (2 cycles)
    code.append(0xE1)                       # POP HL       (3 cycles)

    # Store palette in WRAM buffer
    code.append(0x12)                       # LD [DE], A   (2 cycles)
    code.append(0x13)                       # INC DE       (2 cycles)

    # Decrement counter
    code.append(0x0B)                       # DEC BC       (2 cycles)
    code.append(0x78)                       # LD A, B      (1 cycle)
    code.append(0xB1)                       # OR C         (1 cycle)

    loop_offset = loop_start - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])  # JR NZ, loop (3/2 cycles)

    # ===== Configure HDMA =====
    # Source: WRAM 0xD000
    code.extend([0x3E, 0xD0])              # LD A, 0xD0
    code.extend([0xE0, 0x51])              # LDH [HDMA1], A (source high)
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x52])              # LDH [HDMA2], A (source low)

    # Dest: VRAM at same offset as source (from 0xFFBE)
    code.extend([0xF0, 0xBE])              # LDH A, [0xFFBE]
    code.extend([0xE0, 0x53])              # LDH [HDMA3], A (dest high)
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x54])              # LDH [HDMA4], A (dest low)

    # Switch to VRAM bank 1 for writing attributes
    code.extend([0x3E, 0x01])              # LD A, 1
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # Start HDMA: HBlank mode (0x80) + length-1 (256/16 - 1 = 15 = 0x0F)
    code.extend([0x3E, 0x8F])              # LD A, 0x8F
    code.extend([0xE0, 0x55])              # LDH [HDMA5], A - START TRANSFER

    # Switch back to VRAM bank 0
    code.append(0xAF)                       # XOR A
    code.extend([0xE0, 0x4F])              # LDH [VBK], A

    # ===== Increment batch counter (0-3) =====
    code.extend([0xF0, 0xBC])              # LDH A, [0xFFBC]
    code.append(0x3C)                       # INC A
    code.extend([0xE6, 0x03])              # AND 0x03
    code.extend([0xE0, 0xBC])              # LDH [0xFFBC], A

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                       # RET

    return bytes(code)


def create_combined_with_hdma(palette_loader_addr: int, shadow_main_addr: int, hdma_bg_addr: int) -> bytes:
    """Combined: load palettes, colorize OBJ shadows, HDMA BG colorize, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, hdma_bg_addr & 0xFF, hdma_bg_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # Call DMA routine at 0xFF80
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
    output_rom = Path("rom/working/penta_dragon_dx_v126.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.26: HDMA-Based BG Colorization ===")
    print("  Hardware-assisted attribute streaming")
    print("  256 tiles processed per frame (4 frames = full tilemap)")
    print("  Tile lookup table determines palette per tile ID")
    print("  HDMA transfers attributes during HBlank periods")
    print("  Scroll-safe: attributes tied to tile IDs, not positions")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # Bank 13 layout
    palette_data_addr = 0x6800      # 64 bytes BG + 64 bytes OBJ
    gargoyle_addr = 0x6880          # 8 bytes
    spider_addr = 0x6888            # 8 bytes
    obj_colorizer_addr = 0x6900     # ~90 bytes
    shadow_main_addr = 0x6980       # ~52 bytes
    palette_loader_addr = 0x69E0    # ~70 bytes
    hdma_bg_addr = 0x6A40           # ~100 bytes (NEW)
    combined_addr = 0x6AC0          # ~16 bytes
    lookup_table_addr = 0x6B00      # 256 bytes (NEW)

    # Generate code
    tile_lookup = create_tile_palette_lookup()
    obj_colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(obj_colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    hdma_bg = create_hdma_bg_colorizer(lookup_table_addr)
    combined = create_combined_with_hdma(palette_loader_addr, shadow_main_addr, hdma_bg_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Tile lookup table: {len(tile_lookup)} bytes at 0x{lookup_table_addr:04X}")
    print(f"OBJ colorizer: {len(obj_colorizer)} bytes at 0x{obj_colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"HDMA BG colorizer: {len(hdma_bg)} bytes at 0x{hdma_bg_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Check for overlaps
    if hdma_bg_addr + len(hdma_bg) > combined_addr:
        print(f"WARNING: HDMA routine ({hdma_bg_addr:04X}-{hdma_bg_addr + len(hdma_bg):04X}) overlaps combined!")
    if combined_addr + len(combined) > lookup_table_addr:
        print(f"WARNING: Combined ({combined_addr:04X}-{combined_addr + len(combined):04X}) overlaps lookup table!")

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
    write_to_bank13(hdma_bg_addr, hdma_bg)
    write_to_bank13(combined_addr, combined)
    write_to_bank13(lookup_table_addr, tile_lookup)

    # NOP out original DMA call at 0x06D5
    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    # VBlank hook
    print(f"\nVBlank hook: {len(vblank_hook)} bytes at 0x0824")
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.26 Build Complete ===")


if __name__ == "__main__":
    main()
