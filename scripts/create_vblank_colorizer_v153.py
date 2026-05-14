#!/usr/bin/env python3
"""
v1.53: LCD-off VRAM Bank 1 Initialization via RST 08 Hook

APPROACH: Hook the game's startup VRAM init (at 0x4003) using the unused RST 08 vector.
During LCD-off init, there are NO timing constraints, so we can safely initialize
all of VRAM bank 1 with tile attributes in one go.

Key changes from v1.50-52 (which all failed due to VBlank timing):
- NO runtime VBK switching during gameplay
- ALL attribute init happens ONCE at game startup when LCD is OFF
- Uses RST 08 vector (unused) as trampoline to bank 4
- Bank 4 has free space at 0x13000 (CPU 0x7000)

Technical flow:
1. Game calls VRAM init at 0x4003 (from 0x0A90)
2. 0x4003 is patched to RST 08 (0xCF)
3. RST 08 handler switches to bank 4 and JPs to 0x7000
4. Bank 4 code at 0x7000:
   - Executes original VRAM clear (LD HL,0x9800; LD BC,0x1000; CALL 0x09A8)
   - Switches to VBK=1
   - Initializes 1024 bytes with tile->palette lookup
   - Switches back to VBK=0
   - Switches ROM back to bank 1
   - JPs to 0x400C (continues original init)

This preserves all v1.09 sprite colorization (tile-based + boss detection).
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


def create_bg_tile_lookup_table() -> bytes:
    """
    Create 256-byte lookup table: tile ID -> BG palette number.

    Based on Level 1 tile analysis:
    - 0x00-0x0F: Floor/basic tiles -> palette 0 (blue)
    - 0x10-0x2F: Decorations -> palette 0 (blue)
    - 0x30-0x4B: Structure/walls -> palette 2 (purple)
    - 0x4C-0x4F: Hazards (spikes) -> palette 5 (red)
    - 0x50-0x9F: Extended structure -> palette 2 (purple)
    - 0xA0-0xDF: Items/powerups -> palette 1 (gold/yellow)
    - 0xE0-0xFF: Borders/edges -> palette 2 (purple)
    """
    table = bytearray(256)

    for i in range(256):
        if i < 0x10:
            # Floor/basic - palette 0 (blue)
            table[i] = 0x00
        elif i < 0x30:
            # Decorations - palette 0 (blue)
            table[i] = 0x00
        elif i < 0x4C:
            # Structure/walls - palette 2 (purple)
            table[i] = 0x02
        elif i < 0x50:
            # Hazards (spikes at 0x4C-0x4F) - palette 5 (red/danger)
            table[i] = 0x05
        elif i < 0xA0:
            # Extended structure - palette 2 (purple)
            table[i] = 0x02
        elif i < 0xE0:
            # Items/powerups (0xA0-0xDF) - palette 1 (gold/yellow)
            table[i] = 0x01
        else:
            # Borders/edges - palette 2 (purple)
            table[i] = 0x02

    return bytes(table)


def create_rst08_handler() -> bytes:
    """
    RST 08 handler at 0x0008 (exactly 8 bytes).
    Switches to bank 4 and jumps to our VRAM init wrapper.
    """
    code = bytearray()
    # LD A, 4 - switch to bank 4
    code.extend([0x3E, 0x04])
    # LD [0x2000], A - write to bank register
    code.extend([0xEA, 0x00, 0x20])
    # JP 0x7000 - jump to our code in bank 4
    code.extend([0xC3, 0x00, 0x70])

    assert len(code) == 8, f"RST 08 handler must be exactly 8 bytes, got {len(code)}"
    return bytes(code)


def create_vram_init_wrapper(lookup_table_addr: int) -> bytes:
    """
    VRAM init wrapper at 0x7000 in bank 4.

    This runs during LCD-off init, so NO timing constraints!

    1. Execute original VRAM clear (what 0x4003-0x400B did)
    2. Switch to VRAM bank 1
    3. Initialize all 1024 tilemap bytes with palette attributes from lookup table
    4. Switch back to VRAM bank 0
    5. Switch ROM back to bank 1
    6. JP to 0x400C to continue original init
    """
    code = bytearray()

    # === Original code from 0x4003-0x400B ===
    # LD HL, 0x9800
    code.extend([0x21, 0x00, 0x98])
    # LD BC, 0x1000
    code.extend([0x01, 0x00, 0x10])
    # CALL 0x09A8 (memset - in bank 0, always accessible)
    code.extend([0xCD, 0xA8, 0x09])

    # === Now add VRAM bank 1 initialization ===
    # Save registers
    code.extend([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL

    # Switch to VRAM bank 1
    # LD A, 1
    code.extend([0x3E, 0x01])
    # LDH [0x4F], A (VBK register)
    code.extend([0xE0, 0x4F])

    # Initialize tilemap attributes
    # We'll read from VRAM bank 0 (tile IDs) and write to bank 1 (attributes)
    # But wait - we just cleared bank 0 to 0x00! So all tiles are 0x00.
    # That means all attributes would be palette 0.
    #
    # Actually, this is fine for initial state. The game will update tiles
    # as it loads the level, and we need to handle that separately.
    #
    # For now, let's initialize with palette 0 (which is what we want for
    # the cleared tilemap). When the game loads level data, we'll need
    # another hook to update attributes.
    #
    # SIMPLER: Just clear VRAM bank 1 to 0x00 (palette 0) as well.
    # This ensures clean initial state.

    # LD HL, 0x9800
    code.extend([0x21, 0x00, 0x98])
    # LD BC, 0x0400 (1024 bytes for 32x32 tilemap)
    code.extend([0x01, 0x00, 0x04])
    # LD A, 0 (palette 0)
    code.extend([0x3E, 0x00])

    # Clear loop
    # clear_loop:
    loop_start = len(code)
    # LD [HL], A
    code.append(0x77)
    # INC HL
    code.append(0x23)
    # DEC BC
    code.append(0x0B)
    # LD A, B
    code.append(0x78)
    # OR C
    code.append(0xB1)
    # LD A, 0 (restore A for next iteration)
    code.extend([0x3E, 0x00])
    # JR NZ, clear_loop
    offset = loop_start - len(code) - 2
    code.extend([0x20, offset & 0xFF])

    # Switch back to VRAM bank 0
    # XOR A
    code.append(0xAF)
    # LDH [0x4F], A
    code.extend([0xE0, 0x4F])

    # Restore registers
    code.extend([0xE1, 0xD1, 0xC1])  # POP HL, DE, BC

    # === Switch ROM back to bank 1 and continue ===
    # LD A, 1
    code.extend([0x3E, 0x01])
    # LD [0x2000], A
    code.extend([0xEA, 0x00, 0x20])
    # JP 0x400C (continue original init in bank 1)
    code.extend([0xC3, 0x0C, 0x40])

    return bytes(code)


def create_tile_based_colorizer() -> bytes:
    """
    Tile-based sprite colorizer with boss/miniboss override.
    (Same as v1.09 - handles OBJ/sprite palettes)
    """
    code = bytearray()
    labels = {}
    jumps_to_fix = []

    # LD B, 40
    code.extend([0x06, 0x28])

    # loop_start:
    labels['loop_start'] = len(code)

    # Check if Sara slot (0-3)
    code.extend([0x3E, 0x28])        # LD A, 40
    code.append(0x90)                # SUB B
    code.extend([0xFE, 0x04])        # CP 4
    jumps_to_fix.append((len(code), 'sara_palette'))
    code.extend([0x38, 0x00])        # JR C, sara_palette

    # Read tile (at HL-1)
    code.append(0x2B)                # DEC HL
    code.append(0x7E)                # LD A, [HL]
    code.append(0x23)                # INC HL
    code.append(0x4F)                # LD C, A

    # Check projectile (tile < 0x10)
    code.extend([0xFE, 0x10])        # CP 0x10
    jumps_to_fix.append((len(code), 'projectile_palette'))
    code.extend([0x38, 0x00])        # JR C, projectile_palette

    # Check boss mode (E register)
    code.append(0x7B)                # LD A, E
    code.append(0xB7)                # OR A
    jumps_to_fix.append((len(code), 'boss_palette'))
    code.extend([0x20, 0x00])        # JR NZ, boss_palette

    # Normal mode: tile-based coloring
    code.append(0x79)                # LD A, C

    # Tile 0x40-0x4F: Hornets
    code.extend([0xFE, 0x50])        # CP 0x50
    jumps_to_fix.append((len(code), 'check_hornet'))
    code.extend([0x38, 0x00])        # JR C, check_hornet

    # Tile 0x50-0x5F: Orcs
    code.extend([0xFE, 0x60])        # CP 0x60
    jumps_to_fix.append((len(code), 'orc_palette'))
    code.extend([0x38, 0x00])        # JR C, orc_palette

    # Tile 0x60-0x6F: Humanoids
    code.extend([0xFE, 0x70])        # CP 0x70
    jumps_to_fix.append((len(code), 'humanoid_palette'))
    code.extend([0x38, 0x00])        # JR C, humanoid_palette

    # Tile 0x70-0x7F: Miniboss
    code.extend([0xFE, 0x80])        # CP 0x80
    jumps_to_fix.append((len(code), 'miniboss_palette'))
    code.extend([0x38, 0x00])        # JR C, miniboss_palette

    # Default: palette 4
    labels['default_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # check_hornet:
    labels['check_hornet'] = len(code)
    code.append(0x79)                # LD A, C
    code.extend([0xFE, 0x40])        # CP 0x40
    jumps_to_fix.append((len(code), 'hornet_palette'))
    code.extend([0x30, 0x00])        # JR NC, hornet_palette
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # sara_palette:
    labels['sara_palette'] = len(code)
    code.append(0x7A)                # LD A, D
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # projectile_palette:
    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])        # LD A, 0
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # boss_palette:
    labels['boss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # hornet_palette:
    labels['hornet_palette'] = len(code)
    code.extend([0x3E, 0x04])        # LD A, 4
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # orc_palette:
    labels['orc_palette'] = len(code)
    code.extend([0x3E, 0x05])        # LD A, 5
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # humanoid_palette:
    labels['humanoid_palette'] = len(code)
    code.extend([0x3E, 0x06])        # LD A, 6
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])        # JR apply_palette

    # miniboss_palette:
    labels['miniboss_palette'] = len(code)
    code.extend([0x3E, 0x07])        # LD A, 7

    # apply_palette:
    labels['apply_palette'] = len(code)
    code.append(0x4F)                # LD C, A
    code.append(0x7E)                # LD A, [HL]
    code.extend([0xE6, 0xF8])        # AND 0xF8
    code.append(0xB1)                # OR C
    code.append(0x77)                # LD [HL], A

    # Next sprite
    code.extend([0x23, 0x23, 0x23, 0x23])  # INC HL x4
    code.append(0x05)                # DEC B
    loop_offset = labels['loop_start'] - len(code) - 2
    code.extend([0x20, loop_offset & 0xFF])  # JR NZ, loop_start
    code.append(0xC9)                # RET

    # Fix jumps
    for jr_pos, target_label in jumps_to_fix:
        target = labels[target_label]
        offset = target - (jr_pos + 2)
        code[jr_pos + 1] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """Colorizes BOTH shadow buffers (0xC000 and 0xC100)."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])  # PUSH AF, BC, DE, HL

    # Determine Sara palette (D)
    code.extend([0xF0, 0xBE])        # LDH A, [FFBE]
    code.append(0xB7)                # OR A
    code.extend([0x20, 0x04])        # JR NZ, +4 (Dragon)
    code.extend([0x16, 0x02])        # LD D, 2 (Witch)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x16, 0x01])        # LD D, 1 (Dragon)

    # Check boss flag at 0xFFBF
    code.extend([0xF0, 0xBF])        # LDH A, [0xFFBF]
    code.extend([0xFE, 0x01])        # CP 1
    code.extend([0x28, 0x08])        # JR Z, +8 (Gargoyle)
    code.extend([0xFE, 0x02])        # CP 2
    code.extend([0x28, 0x06])        # JR Z, +6 (Spider)
    code.extend([0x1E, 0x00])        # LD E, 0 (normal)
    code.extend([0x18, 0x06])        # JR +6
    code.extend([0x1E, 0x06])        # LD E, 6 (Gargoyle)
    code.extend([0x18, 0x02])        # JR +2
    code.extend([0x1E, 0x07])        # LD E, 7 (Spider)

    # Colorize shadow buffer 1
    code.extend([0x21, 0x03, 0xC0])  # LD HL, 0xC003
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    # Colorize shadow buffer 2
    code.extend([0x21, 0x03, 0xC1])  # LD HL, 0xC103
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1])  # POP HL, DE, BC, AF
    code.append(0xC9)                # RET
    return bytes(code)


def create_palette_loader(palette_data_addr: int, gargoyle_addr: int, spider_addr: int) -> bytes:
    """Load CGB palettes with dynamic boss palette swapping."""
    code = bytearray()

    # Load BG palettes (64 bytes)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x0E, 0x40])
    code.extend([0x2A])
    code.extend([0xE0, 0x69])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    # Load OBJ palettes 0-5 (48 bytes)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x30])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    # Palette 6: Check for Gargoyle
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A])
    code.extend([0xE0, 0x6B])
    code.extend([0x0D])
    code.extend([0x20, 0xFA])

    # Palette 7: Check for Spider
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


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int) -> bytes:
    """Combined function: load palettes, colorize shadows, run DMA."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])
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
    output_rom = Path("rom/working/penta_dragon_dx_v153.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.53: LCD-off VRAM Bank 1 Initialization ===")
    print("  Hook VRAM init at 0x4003 via unused RST 08 vector")
    print("  Initialize VRAM bank 1 during LCD-off (no timing constraints)")
    print("  Preserves v1.09 sprite colorization (tile-based + boss detection)")
    print()

    rom = bytearray(input_rom.read_bytes())
    apply_all_display_patches(rom)

    # === RST 08 Handler at 0x0008 ===
    rst08_handler = create_rst08_handler()
    print(f"RST 08 handler: {len(rst08_handler)} bytes at 0x0008")
    rom[0x0008:0x0008 + len(rst08_handler)] = rst08_handler

    # === Patch 0x4003 to RST 08 ===
    print(f"Original at 0x4003: {rom[0x4003:0x400C].hex()}")
    rom[0x4003] = 0xCF  # RST 08
    # NOP out the rest to be safe (0x4004-0x400B)
    for i in range(0x4004, 0x400C):
        rom[i] = 0x00
    print(f"Patched 0x4003: CF (RST 08) + NOPs")

    # === VRAM Init Wrapper in Bank 4 at 0x7000 (ROM offset 0x13000) ===
    lookup_table_addr = 0x7100  # Will place lookup table here
    vram_init_wrapper = create_vram_init_wrapper(lookup_table_addr)
    bank4_offset = 4 * 0x4000  # 0x10000
    wrapper_rom_offset = bank4_offset + (0x7000 - 0x4000)  # 0x13000
    print(f"VRAM init wrapper: {len(vram_init_wrapper)} bytes at ROM 0x{wrapper_rom_offset:05X} (CPU 0x7000)")
    rom[wrapper_rom_offset:wrapper_rom_offset + len(vram_init_wrapper)] = vram_init_wrapper

    # === Tile->Palette Lookup Table at 0x7100 (ROM offset 0x13100) ===
    lookup_table = create_bg_tile_lookup_table()
    lookup_rom_offset = bank4_offset + (0x7100 - 0x4000)  # 0x13100
    print(f"BG tile lookup table: {len(lookup_table)} bytes at ROM 0x{lookup_rom_offset:05X}")
    rom[lookup_rom_offset:lookup_rom_offset + len(lookup_table)] = lookup_table

    # === Bank 13 Layout (same as v1.09) ===
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    colorizer_addr = 0x6900
    shadow_main_addr = 0x6980
    palette_loader_addr = 0x69E0
    combined_addr = 0x6A80

    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    rom[bank13_offset + (colorizer_addr - 0x4000):bank13_offset + (colorizer_addr - 0x4000) + len(colorizer)] = colorizer
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined

    # NOP out DMA at 0x06D5
    print(f"\nOriginal at 0x06D5: {rom[0x06D5:0x06D8].hex()}")
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    print("Patched 0x06D5: 00 00 00 (NOP)")

    # Write VBlank hook
    print(f"\nVBlank hook: {len(vblank_hook)} bytes")
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # Set CGB flag
    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.53 Build Complete ===")
    print("\nNote: This version initializes VRAM bank 1 at startup.")
    print("BG tiles will use palette 0 (blue) initially.")
    print("For dynamic BG coloring during gameplay, we need to hook the tilemap updater.")


if __name__ == "__main__":
    main()
