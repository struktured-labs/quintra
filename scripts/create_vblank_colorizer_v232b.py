#!/usr/bin/env python3
"""
v2.32b: DIAGNOSTIC BUILD - v2.31 palette loader + v2.32 colorizer

PURPOSE: Isolate whether the gray projectile bug is in v2.32's palette loader
or v2.32's colorizer.

PALETTE LOADER: Exact copy from v2.31 (Sara form check, NO powerup code)
COLORIZER: From v2.32 (per-entity projectile tile detection, JP NZ loop)

If this build shows pink Sara W projectiles: Bug is in v2.32's palette loader.
If this build shows gray Sara W projectiles: Bug is in v2.32's colorizer.
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
    """Load palettes from YAML (v2.31 signature - no powerup palettes)."""
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

    obj_keys = ['SaraProjectileWitch', 'SaraDragon', 'SaraWitch', 'Crow',
                'Hornets', 'OrcGround', 'Humanoid', 'Catfish']
    obj_data = bytearray()
    for key in obj_keys:
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            if key == 'SaraProjectileWitch':
                obj_data.extend(pal_to_bytes(["0000", "7C1F", "5817", "3010"]))
            else:
                obj_data.extend(pal_to_bytes(["0000", "7FFF", "5294", "2108"]))

    boss_data = data.get('boss_palettes', {})
    gargoyle = pal_to_bytes(boss_data.get('Gargoyle', {}).get('colors', ["0000", "601F", "400F", "0000"]))
    spider = pal_to_bytes(boss_data.get('Spider', {}).get('colors', ["0000", "001F", "00BF", "0000"]))

    jet_data = data.get('obj_palettes', {})
    sara_witch_jet = pal_to_bytes(jet_data.get('SaraWitchJet', {}).get('colors', ["0000", "7C1F", "5817", "3010"]))
    sara_dragon_jet = pal_to_bytes(jet_data.get('SaraDragonJet', {}).get('colors', ["0000", "7FE0", "4EC0", "2D80"]))

    return bytes(bg_data), bytes(obj_data), gargoyle, spider, sara_witch_jet, sara_dragon_jet


def create_tile_based_colorizer(colorizer_base_addr: int) -> bytes:
    """
    Tile-based colorizer with per-entity projectile detection (from v2.32).
    Uses JP NZ for loop (code > 128 bytes).
    """
    code = bytearray()
    labels = {}
    forward_jumps = []

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def emit_jr(opcode, target_label):
        code.append(opcode)
        forward_jumps.append((len(code), target_label))
        code.append(0x00)

    # === MAIN LOOP ===
    emit([0x06, 0x28])  # LD B, 40
    labels['loop_start'] = len(code)

    # Check if Sara slot (0-3)
    emit([0x3E, 0x28, 0x90, 0xFE, 0x04])  # LD A, 40; SUB B; CP 4
    emit_jr(0x38, 'sara_palette')  # JR C, sara_palette

    # Read tile into C
    emit([0x2B, 0x7E, 0x23, 0x4F])  # DEC HL; LD A, [HL]; INC HL; LD C, A

    # === PROJECTILE CHECK (tiles 0x00-0x0F) ===
    emit([0xFE, 0x10])  # CP 0x10
    emit_jr(0x30, 'check_higher_tiles')  # JR NC, check_higher_tiles

    # Tile 0x0F = Sara W projectile
    emit([0xFE, 0x0F])  # CP 0x0F
    emit_jr(0x28, 'pal_sara_w_proj')

    # Tiles 0x06, 0x09, 0x0A = Sara D projectile
    emit([0xFE, 0x06])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x09])
    emit_jr(0x28, 'pal_sara_d_proj')
    emit([0xFE, 0x0A])
    emit_jr(0x28, 'pal_sara_d_proj')

    # Tiles 0x00-0x01 = enemy projectile
    emit([0xFE, 0x02])
    emit_jr(0x38, 'pal_enemy_proj')  # JR C

    # Default projectile palette (tiles 0x02-0x05, 0x07-0x08, 0x0B-0x0E)
    emit([0x3E, 0x00])  # LD A, 0
    emit_jr(0x18, 'apply_palette')

    # === HIGHER TILE CHECKS (0x10+) ===
    labels['check_higher_tiles'] = len(code)

    # Effect range 0x10-0x1F
    emit([0xFE, 0x20])
    emit_jr(0x30, 'check_sara_sprite')  # JR NC
    emit([0x3E, 0x04])  # LD A, 4 (effects)
    emit_jr(0x18, 'apply_palette')

    # Sara sprite range 0x20-0x2F
    labels['check_sara_sprite'] = len(code)
    emit([0xFE, 0x30])
    emit_jr(0x38, 'sara_palette')

    # Check boss mode
    emit([0x7B, 0xB7])  # LD A, E; OR A
    emit_jr(0x20, 'boss_palette')

    # === ENEMY TILE RANGES ===
    emit(0x79)  # LD A, C
    emit([0xFE, 0x50])
    emit_jr(0x38, 'check_crow_hornet')

    emit([0xFE, 0x60])
    emit_jr(0x38, 'pal_orc')

    emit([0xFE, 0x70])
    emit_jr(0x38, 'pal_humanoid')

    emit([0xFE, 0x80])
    emit_jr(0x38, 'pal_catfish')

    # Default palette
    emit([0x3E, 0x04])  # LD A, 4
    emit_jr(0x18, 'apply_palette')

    # === SUB-CHECKS ===
    labels['check_crow_hornet'] = len(code)
    emit([0x79, 0xFE, 0x40])  # LD A, C; CP 0x40
    emit_jr(0x30, 'pal_hornet')  # JR NC (0x40-0x4F)
    # Fall through for crow (0x30-0x3F)
    emit([0x3E, 0x03])  # LD A, 3
    emit_jr(0x18, 'apply_palette')

    # === PALETTE HANDLERS ===
    labels['pal_sara_w_proj'] = len(code)
    emit([0x3E, 0x02])  # LD A, 2 (Palette 2 = Sara W skin/pink - DIAGNOSTIC)
    emit_jr(0x18, 'apply_palette')

    labels['pal_sara_d_proj'] = len(code)
    emit([0x3E, 0x00])  # LD A, 0 (Palette 0 = dynamic green when Sara D)
    emit_jr(0x18, 'apply_palette')

    labels['pal_enemy_proj'] = len(code)
    emit([0x3E, 0x03])  # LD A, 3 (dark blue)
    emit_jr(0x18, 'apply_palette')

    labels['pal_hornet'] = len(code)
    emit([0x3E, 0x04])  # LD A, 4
    emit_jr(0x18, 'apply_palette')

    labels['pal_orc'] = len(code)
    emit([0x3E, 0x05])  # LD A, 5
    emit_jr(0x18, 'apply_palette')

    labels['pal_humanoid'] = len(code)
    emit([0x3E, 0x06])  # LD A, 6
    emit_jr(0x18, 'apply_palette')

    labels['pal_catfish'] = len(code)
    emit([0x3E, 0x07])  # LD A, 7
    emit_jr(0x18, 'apply_palette')

    labels['sara_palette'] = len(code)
    emit(0x7A)  # LD A, D
    emit_jr(0x18, 'apply_palette')

    labels['boss_palette'] = len(code)
    emit(0x7B)  # LD A, E
    # Fall through to apply_palette

    # === APPLY PALETTE ===
    labels['apply_palette'] = len(code)
    emit([0x4F])        # LD C, A
    emit([0x7E])        # LD A, [HL]
    emit([0xE6, 0xF8])  # AND 0xF8
    emit([0xB1])        # OR C
    emit([0x77])        # LD [HL], A

    # Next sprite
    emit([0x23, 0x23, 0x23, 0x23])  # INC HL x4
    emit([0x05])        # DEC B
    # Use JP NZ (code > 128 bytes)
    loop_abs_addr = colorizer_base_addr + labels['loop_start']
    emit([0xC2, loop_abs_addr & 0xFF, (loop_abs_addr >> 8) & 0xFF])
    emit([0xC9])        # RET

    # === FIX ALL FORWARD JUMPS ===
    for offset_pos, target_label in forward_jumps:
        target = labels[target_label]
        offset = target - (offset_pos + 1)
        if offset < -128 or offset > 127:
            raise ValueError(f"Jump to {target_label} out of range: {offset}")
        code[offset_pos] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int) -> bytes:
    """Shadow colorizer (identical to v2.31)."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    code.extend([0xF0, 0xBE, 0xB7, 0x20, 0x04])
    code.extend([0x16, 0x02, 0x18, 0x02])
    code.extend([0x16, 0x01])

    code.extend([0xF0, 0xBF, 0xFE, 0x01, 0x28, 0x08])
    code.extend([0xFE, 0x02, 0x28, 0x08])
    code.extend([0x1E, 0x00, 0x18, 0x06])
    code.extend([0x1E, 0x06, 0x18, 0x02])
    code.extend([0x1E, 0x07])

    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1, 0xC9])
    return bytes(code)


def create_palette_loader(
    palette_data_addr: int,
    gargoyle_addr: int,
    spider_addr: int,
    sara_witch_jet_addr: int,
    sara_dragon_jet_addr: int,
    sara_projectile_dragon_addr: int
) -> bytes:
    """
    EXACT COPY of v2.31 palette loader.
    Sara form-based dynamic Palette 0, NO powerup code.
    """
    code = bytearray()

    # Check stage flag and save in D register
    code.extend([0xF0, 0xD0])  # LDH A, [0xFFD0]
    code.append(0x57)  # LD D, A

    # Check boss flag and save in E register
    code.extend([0xF0, 0xBF])  # LDH A, [0xFFBF]
    code.append(0x5F)  # LD E, A

    # Load BG palettes (64 bytes)
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 0 (Sara projectiles - dynamic based on form)
    obj_data_addr = palette_data_addr + 64
    code.extend([0x3E, 0x80, 0xE0, 0x6A])  # Set OCPS to palette 0
    code.extend([0xF0, 0xBE])  # LDH A, [0xFFBE]
    code.extend([0xB7])  # OR A
    code.extend([0x20, 0x05])  # JR NZ, +5
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x18, 0x03])  # JR +3
    code.extend([0x21, sara_projectile_dragon_addr & 0xFF, (sara_projectile_dragon_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 1 (Sara Dragon - check stage)
    code.extend([0x3E, 0x88, 0xE0, 0x6A])
    sara_dragon_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_addr & 0xFF, (sara_dragon_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 2 (Sara Witch - check stage)
    code.extend([0x3E, 0x90, 0xE0, 0x6A])
    sara_witch_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_addr & 0xFF, (sara_witch_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Load OBJ palettes 3-5 (Crow, Hornets, Orc)
    code.extend([0x3E, 0x98, 0xE0, 0x6A])
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 6 (Humanoid or Gargoyle)
    code.extend([0x3E, 0xB0, 0xE0, 0x6A])
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0x7B, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    # Load OBJ palette 7 (Catfish or Spider)
    code.extend([0x3E, 0xB8, 0xE0, 0x6A])
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0x7B, 0xFE, 0x02, 0x20, 0x03])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.append(0xC9)
    return bytes(code)


def create_tile_palette_lookup() -> bytes:
    """256-byte lookup table: tile_id -> BG palette."""
    lookup = bytearray(256)
    for i in range(256):
        if i < 0x20:
            lookup[i] = 0
        elif i < 0x80:
            lookup[i] = 2
        elif i < 0xE0:
            lookup[i] = 1
        elif i == 0xFF:
            lookup[i] = 0
        else:
            lookup[i] = 2
    return bytes(lookup)


def create_bg_colorizer_oneshot(lookup_table_addr: int) -> bytes:
    """One-shot BG colorizer (unchanged)."""
    code = bytearray()
    code.extend([0xF0, 0xE0, 0xFE, 0x12, 0xD0])
    code.extend([0xC5, 0xD5, 0x6F, 0x26, 0x00])
    code.extend([0x29, 0x29, 0x29, 0x29, 0x29])
    code.extend([0x01, 0x00, 0x98, 0x09, 0x06, 0x20])

    tile_loop_start = len(code)
    code.extend([0xAF, 0xE0, 0x4F, 0x56])
    code.extend([0xE5, 0x26, (lookup_table_addr >> 8) & 0xFF])
    code.extend([0x7A, 0x6F, 0x5E, 0xE1])
    code.extend([0x3E, 0x01, 0xE0, 0x4F, 0x73])
    code.extend([0x23, 0x05])
    tile_offset = tile_loop_start - len(code) - 2
    code.extend([0x20, tile_offset & 0xFF])

    code.extend([0xD1, 0xC1])
    code.extend([0xF0, 0xE0, 0xC6, 0x01, 0xE0, 0xE0])
    code.extend([0xAF, 0xE0, 0x4F, 0xC9])
    return bytes(code)


def create_combined_with_dma(palette_loader_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined function."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF, 0xC9])
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
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.32b (DIAGNOSTIC) ===")
    print("v2.31 palette loader + v2.32 colorizer")
    print()
    print("PURPOSE: Isolate gray projectile bug")
    print("  If pink: Bug is in v2.32's palette loader (powerup code)")
    print("  If gray: Bug is in v2.32's colorizer (per-entity tiles)")
    print()

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)

    bg_data, obj_data, gargoyle, spider, sara_witch_jet, sara_dragon_jet = load_palettes_from_yaml(palette_yaml)
    sara_projectile_dragon = obj_data[8:16]  # Copy palette 1 (Sara D) for dynamic Palette 0

    # Bank 13 layout (same as v2.31 addresses where possible)
    palette_data_addr = 0x6800
    gargoyle_addr = 0x6880
    spider_addr = 0x6888
    sara_witch_jet_addr = 0x6890
    sara_dragon_jet_addr = 0x6898
    sara_projectile_dragon_addr = 0x68A0
    palette_loader_addr = 0x6900
    shadow_main_addr = 0x69B0
    colorizer_addr = 0x69F0  # Same as v2.31 - v2.31's palette loader fits by 0x69B0
    lookup_table_addr = 0x6B00
    bg_colorizer_addr = 0x6C00
    combined_addr = 0x6D00

    palette_loader = create_palette_loader(
        palette_data_addr, gargoyle_addr, spider_addr,
        sara_witch_jet_addr, sara_dragon_jet_addr,
        sara_projectile_dragon_addr
    )
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    lookup_table = create_tile_palette_lookup()
    bg_colorizer = create_bg_colorizer_oneshot(lookup_table_addr)
    combined = create_combined_with_dma(palette_loader_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")

    # Verify no overlaps
    palette_loader_end = palette_loader_addr + len(palette_loader)
    shadow_main_end = shadow_main_addr + len(shadow_main)
    colorizer_end = colorizer_addr + len(colorizer)
    print(f"  Palette loader ends at 0x{palette_loader_end:04X} (shadow main starts at 0x{shadow_main_addr:04X})")
    print(f"  Shadow main ends at 0x{shadow_main_end:04X} (colorizer starts at 0x{colorizer_addr:04X})")
    print(f"  Colorizer ends at 0x{colorizer_end:04X} (lookup table starts at 0x{lookup_table_addr:04X})")

    if palette_loader_end > shadow_main_addr:
        print(f"ERROR: Palette loader overlaps shadow main!")
        return
    if shadow_main_end > colorizer_addr:
        print(f"ERROR: Shadow main overlaps colorizer!")
        return
    if colorizer_end > lookup_table_addr:
        print(f"ERROR: Colorizer overlaps lookup table!")
        return

    bank13_offset = 13 * 0x4000

    rom[bank13_offset + (palette_data_addr - 0x4000):bank13_offset + (palette_data_addr - 0x4000) + len(bg_data)] = bg_data
    rom[bank13_offset + (palette_data_addr - 0x4000) + 64:bank13_offset + (palette_data_addr - 0x4000) + 64 + len(obj_data)] = obj_data
    rom[bank13_offset + (gargoyle_addr - 0x4000):bank13_offset + (gargoyle_addr - 0x4000) + len(gargoyle)] = gargoyle
    rom[bank13_offset + (spider_addr - 0x4000):bank13_offset + (spider_addr - 0x4000) + len(spider)] = spider
    rom[bank13_offset + (sara_witch_jet_addr - 0x4000):bank13_offset + (sara_witch_jet_addr - 0x4000) + len(sara_witch_jet)] = sara_witch_jet
    rom[bank13_offset + (sara_dragon_jet_addr - 0x4000):bank13_offset + (sara_dragon_jet_addr - 0x4000) + len(sara_dragon_jet)] = sara_dragon_jet
    rom[bank13_offset + (sara_projectile_dragon_addr - 0x4000):bank13_offset + (sara_projectile_dragon_addr - 0x4000) + len(sara_projectile_dragon)] = sara_projectile_dragon
    rom[bank13_offset + (palette_loader_addr - 0x4000):bank13_offset + (palette_loader_addr - 0x4000) + len(palette_loader)] = palette_loader
    rom[bank13_offset + (shadow_main_addr - 0x4000):bank13_offset + (shadow_main_addr - 0x4000) + len(shadow_main)] = shadow_main
    rom[bank13_offset + (colorizer_addr - 0x4000):bank13_offset + (colorizer_addr - 0x4000) + len(colorizer)] = colorizer
    rom[bank13_offset + (lookup_table_addr - 0x4000):bank13_offset + (lookup_table_addr - 0x4000) + len(lookup_table)] = lookup_table
    rom[bank13_offset + (bg_colorizer_addr - 0x4000):bank13_offset + (bg_colorizer_addr - 0x4000) + len(bg_colorizer)] = bg_colorizer
    rom[bank13_offset + (combined_addr - 0x4000):bank13_offset + (combined_addr - 0x4000) + len(combined)] = combined

    rom[0x06D5:0x06D5 + 3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    rom[0x143] = 0x80
    print("Set CGB flag at 0x143")

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom)

    print(f"\n✓ ROM patched successfully")
    print(f"  Output: {output_rom}")
    print(f"\nDIAGNOSTIC: If Sara W projectiles are pink, bug is in v2.32 palette loader.")
    print(f"DIAGNOSTIC: If Sara W projectiles are gray, bug is in v2.32 colorizer.")


if __name__ == "__main__":
    main()
