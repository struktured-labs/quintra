#!/usr/bin/env python3
"""
v1.47: ROM-Level BG Attribute Initialization

Instead of runtime VRAM bank switching (which causes flicker),
we hook the game's VRAM initialization at 0x0A90.

When the game clears VRAM (LCD is OFF), we ALSO initialize VRAM bank 1
with tile attributes. Since LCD is off, there's no timing conflict.

Hook point: 0x0A90 (CALL 0x4003 - VRAM clear during init)
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    def pal_to_bytes(colors):
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


def create_tile_based_colorizer():
    """Sprite colorizer from v1.09 (unchanged)."""
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
    code.append(0xE5)
    code.extend([0x26, 0xC0])
    code.append(0x6F)
    code.append(0x2B)
    code.append(0x2B)
    code.append(0x7E)
    code.append(0xE1)
    code.extend([0xE6, 0x08])
    jumps_to_fix.append((len(code), 'sara_w'))
    code.extend([0x28, 0x00])
    code.extend([0x3E, 0x01])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['sara_w'] = len(code)
    code.extend([0x3E, 0x02])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['projectile_palette'] = len(code)
    code.extend([0x3E, 0x00])
    jumps_to_fix.append((len(code), 'apply_palette'))
    code.extend([0x18, 0x00])
    labels['boss_palette'] = len(code)
    code.append(0x5F)
    code.extend([0x3E, 0x06])
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
    code.extend([0x3E, 0x03])
    labels['apply_palette'] = len(code)
    code.append(0x2B)
    code.append(0x46)
    code.extend([0xE6, 0x07])
    code.append(0xB0)
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


def create_shadow_colorizer_main(colorizer_addr):
    """Shadow OAM colorizer (unchanged from v1.09)."""
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


def create_vram_init_wrapper():
    """
    Wrapper for VRAM initialization that also sets up VRAM bank 1.

    Called instead of original CALL 0x4003.
    LCD is OFF at this point, so VRAM is fully accessible.

    Steps:
    1. Call original 0x4003 (clear VRAM bank 0)
    2. Switch to VRAM bank 1
    3. Clear VRAM 0x9800-0x9BFF with palette 0 (default)
    4. Switch back to VRAM bank 0
    5. Return
    """
    code = bytearray()

    # Call original VRAM clear (0x4003)
    # We're in bank 13, but 0x4003 is in bank 1
    # Need to switch banks
    code.extend([0xF5])                 # PUSH AF (save A)
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xEA, 0x00, 0x20])     # LD [0x2000], A (switch to ROM bank 1)
    code.extend([0xCD, 0x03, 0x40])     # CALL 0x4003 (original VRAM clear)
    code.extend([0x3E, 0x0D])           # LD A, 13
    code.extend([0xEA, 0x00, 0x20])     # LD [0x2000], A (switch back to bank 13)
    code.extend([0xF1])                 # POP AF

    # Now initialize VRAM bank 1 with default attribute (palette 0)
    # LCD is still OFF, so this is safe
    code.extend([0x3E, 0x01])           # LD A, 1
    code.extend([0xE0, 0x4F])           # LDH [VBK], A (switch to VRAM bank 1)

    # Clear 0x9800-0x9BFF (1KB tilemap) with palette 0
    code.extend([0x21, 0x00, 0x98])     # LD HL, 0x9800
    code.extend([0x01, 0x00, 0x04])     # LD BC, 0x0400 (1024 bytes)
    code.extend([0xAF])                 # XOR A (A = 0, palette 0)
    # Loop: fill with A
    loop_start = len(code)
    code.append(0x22)                   # LD [HL+], A
    code.append(0x0B)                   # DEC BC
    code.append(0x78)                   # LD A, B
    code.append(0xB1)                   # OR C
    code.append(0xAF)                   # XOR A (restore A = 0 for next iteration)
    jump_offset = loop_start - len(code) - 2
    code.extend([0x20, jump_offset & 0xFF])  # JR NZ, loop

    # Switch back to VRAM bank 0
    code.extend([0xE0, 0x4F])           # LDH [VBK], A (A is already 0)

    code.append(0xC9)                   # RET

    return bytes(code)


def create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr):
    """Palette loader (unchanged from v1.09)."""
    code = bytearray()
    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x68])
    code.extend([0x06, 0x40])
    code.append(0x2A)
    code.extend([0xE0, 0x69])
    code.append(0x05)
    code.extend([0x20, 0xFA])
    obj_data_addr = palette_data_addr + 64
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x06, 0x30])
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x05)
    code.extend([0x20, 0xFA])
    pal6_normal_addr = obj_data_addr + 48
    code.extend([0x21, pal6_normal_addr & 0xFF, (pal6_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x03])
    code.extend([0x21, gargoyle_addr & 0xFF, (gargoyle_addr >> 8) & 0xFF])
    code.extend([0x3E, 0xB0])
    code.extend([0xE0, 0x6A])
    code.extend([0x0E, 0x08])
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x0D)
    code.extend([0x20, 0xFA])
    pal7_normal_addr = obj_data_addr + 56
    code.extend([0x21, pal7_normal_addr & 0xFF, (pal7_normal_addr >> 8) & 0xFF])
    code.extend([0xF0, 0xBF])
    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x03])
    code.extend([0x21, spider_addr & 0xFF, (spider_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.append(0x2A)
    code.extend([0xE0, 0x6B])
    code.append(0x0D)
    code.extend([0x20, 0xFA])
    code.append(0xC9)
    return bytes(code)


def create_combined_func(palette_loader_addr, shadow_main_addr):
    """Combined function for VBlank (sprites only, no BG)."""
    code = bytearray()
    code.extend([0xCD, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF])  # Original input handler
    code.append(0xC9)
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr):
    """VBlank hook (unchanged)."""
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
    output_rom = Path("rom/working/penta_dragon_dx_v147.gb")
    fixed_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_path = Path("palettes/penta_palettes_v097.yaml")

    print(f"Loading palettes from: {palette_path}")
    bg_data, obj_data, gargoyle, spider = load_palettes_from_yaml(palette_path)

    print("\n=== v1.47: ROM-Level BG Attribute Init ===")
    print("  Hooks VRAM init at 0x0A90 (LCD is OFF)")
    print("  Initializes VRAM bank 1 during game startup")
    print("  NO runtime VRAM bank switching = NO flicker")
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
    combined_addr = 0x6A80
    vram_init_wrapper_addr = 0x6AC0

    # Generate code
    colorizer = create_tile_based_colorizer()
    shadow_main = create_shadow_colorizer_main(colorizer_addr)
    palette_loader = create_palette_loader(palette_data_addr, gargoyle_addr, spider_addr)
    combined = create_combined_func(palette_loader_addr, shadow_main_addr)
    vram_init_wrapper = create_vram_init_wrapper()
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    print(f"Sprite colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Combined func: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"VRAM init wrapper: {len(vram_init_wrapper)} bytes at 0x{vram_init_wrapper_addr:04X}")

    # Write to bank 13
    bank13_offset = 13 * 0x4000

    def write_to_bank13(addr, data):
        offset = bank13_offset + (addr - 0x4000)
        rom[offset:offset + len(data)] = data

    write_to_bank13(palette_data_addr, bg_data)
    write_to_bank13(palette_data_addr + 64, obj_data)
    write_to_bank13(gargoyle_addr, gargoyle)
    write_to_bank13(spider_addr, spider)
    write_to_bank13(colorizer_addr, colorizer)
    write_to_bank13(shadow_main_addr, shadow_main)
    write_to_bank13(palette_loader_addr, palette_loader)
    write_to_bank13(combined_addr, combined)
    write_to_bank13(vram_init_wrapper_addr, vram_init_wrapper)

    # Patch original VBlank
    rom[0x06D5:0x06D8] = bytes([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    # HOOK: Patch CALL 0x4003 at 0x0A90 to call our wrapper
    # Original: CD 03 40 (CALL 0x4003)
    # New: CD C0 6A (CALL 0x6AC0) - but need to switch to bank 13 first
    #
    # Actually, we need a trampoline since 0x0A90 is in bank 0 and our code is in bank 13
    # Let's put a small trampoline in bank 0 free space
    #
    # For now, let's try a simpler approach: modify the 0x4003 routine itself
    # to also clear VRAM bank 1

    # Simpler approach: Patch 0x4003 directly to also clear VRAM bank 1
    # 0x4003 is in bank 1, so we can modify it
    # But it's called with LCD off, so we can add our code

    # Actually, let's patch at a free spot in bank 0 near 0x0A90
    # Or use RST vectors if any are free

    # Simplest: Just modify the routine at 0x4003 directly
    # Current:
    #   4003: 21 00 98     LD HL,0x9800
    #   4006: 01 00 10     LD BC,0x1000
    #   4009: CD A8 09     CALL 0x09A8
    #   400C: CD 22 44     CALL 0x4422
    #
    # We'll inject a CALL to our VRAM bank 1 init after the first memset
    # But we need space... let's check if there's room

    # Alternative: Patch the CALL at 0x0A90 to our init wrapper
    # The wrapper will be in bank 0 (where there's space)

    # Let me put the init wrapper in the VBlank hook area since we have space there
    # Actually, let's just expand the VBlank hook to include VRAM init

    # For v1.47, let's try the simplest thing that could work:
    # Put a hook at 0x0A93 (after CALL 0x4003) that jumps to our VRAM bank 1 init
    # 0x0A93 is RST 28 (EF) - 1 byte
    # We need 3 bytes for CALL...

    # Let's try patching the CALL 0x4003 at 0x0A90
    # Original: CD 03 40
    # We need to call our wrapper in bank 13
    #
    # Trampoline at 0x0A90:
    #   Save current bank (read from 0xFF99 or just assume bank 0)
    #   Switch to bank 13
    #   CALL vram_init_wrapper
    #   Switch back to bank 1 (or 0?)
    #   Continue
    #
    # This needs more than 3 bytes...

    # Let's try: hijack the RST 28 at 0x0A93
    # RST 28 jumps to 0x0028
    # We could put our init code at 0x0028 and have it also do RST 28's job
    # But that's risky...

    # Simplest safe approach for v1.47:
    # Don't hook VRAM init at all
    # Just verify v1.09 sprites work, then we'll figure out BG later

    # Actually, let me try ONE more thing:
    # The VBlank hook runs every frame. On the FIRST frame only,
    # we can check if VRAM bank 1 needs init and do it then
    # (but only if LCD is in VBlank, which it should be)

    # For now, let's just build v1.47 as v1.09 (sprites only)
    # and add the VRAM init hook in a follow-up

    rom[0x143] = 0x80  # CGB flag

    output_rom.write_bytes(rom)
    fixed_rom.write_bytes(rom)

    print(f"\nWrote: {output_rom}")
    print(f"Wrote: {fixed_rom}")
    print("\n=== v1.47 Build Complete ===")
    print("\nNOTE: v1.47 is currently same as v1.09 (sprites only)")
    print("VRAM bank 1 init hook needs more investigation")


if __name__ == "__main__":
    main()
