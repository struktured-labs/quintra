#!/usr/bin/env python3
"""
v2.63: High-speed BG sweep with 0xFF anti-flicker filter (MiSTer-optimized)

STAT waits made flicker WORSE on MiSTer: slower sweep (71 tiles vs 109) and
VBK bank switching during HBlank caused visual artifacts on the FPGA.

Fix: Remove STAT waits entirely, restore the 0xFF anti-flicker filter, and
increase tiles/frame to 157 for the fastest possible sweep.

How the 0xFF filter works:
- During PPU mode 3, VRAM reads return 0xFF (garbage)
- ROM lookup table maps tile 0xFF → 0xFF (skip marker)
- Caller sees 0xFF → skips the VBK switch + write entirely
- Existing correct palette attributes are NEVER damaged
- Accuracy monotonically increases: tiles only get better, never worse

Key features:
- NO STAT waits (faster sweep, no mid-frame VBK artifacts)
- 0xFF anti-flicker filter (INC A / JR Z skip / DEC A)
- 157 tiles/frame (prime, 1024/157 = 6.5 frames = 0.11s settling)
- Single active tilemap via LCDC bit 3 detection
- Safe HRAM: FF91=counter_lo, FFA5=counter_hi, FFA9=palette_hash_cache
- ROM lookup table at bg_table_addr (H register holds high byte)
"""
import sys
import yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from penta_dragon_dx.display_patcher import apply_all_display_patches


def load_palettes_from_yaml(yaml_path: Path) -> dict:
    """Load all palette data from YAML file."""
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

    obj_key_map = {
        0: ('EnemyProjectile', ["0000", "7C1F", "5817", "3010"]),
        1: ('SaraDragon', ["0000", "03E0", "01C0", "0000"]),
        2: ('SaraWitch', ["0000", "2EBE", "511F", "0842"]),
        3: ('SaraProjectileAndCrow', ["0000", "001F", "0017", "000F"]),
        4: ('Hornets', ["0000", "03FF", "00DF", "0000"]),
        5: ('OrcGround', ["0000", "02A0", "0160", "0000"]),
        6: ('Humanoid', ["0000", "7C1F", "4C0F", "0000"]),
        7: ('Catfish', ["0000", "7FE0", "3CC0", "0000"]),
    }
    obj_data = bytearray()
    for i in range(8):
        key, fallback = obj_key_map[i]
        if key in data.get('obj_palettes', {}):
            obj_data.extend(pal_to_bytes(data['obj_palettes'][key]['colors']))
        else:
            obj_data.extend(pal_to_bytes(fallback))

    boss_keys = ['Gargoyle', 'Spider', 'Boss3_Crimson', 'Boss4_Ice',
                 'Boss5_Void', 'Boss6_Poison', 'Boss7_Knight', 'Angela']
    boss_data = data.get('boss_palettes', {})
    boss_palette_table = bytearray()
    boss_slot_table = bytearray()
    for key in boss_keys:
        entry = boss_data.get(key, {})
        colors = entry.get('colors', ["0000", "7FFF", "5294", "2108"])
        slot = entry.get('slot', 6)
        boss_palette_table.extend(pal_to_bytes(colors))
        boss_slot_table.append(slot)

    jet_data = data.get('obj_palettes', {})
    sara_witch_jet = pal_to_bytes(jet_data.get('SaraWitchJet', {}).get('colors', ["0000", "7C1F", "5817", "3010"]))
    sara_dragon_jet = pal_to_bytes(jet_data.get('SaraDragonJet', {}).get('colors', ["0000", "7FE0", "4EC0", "2D80"]))

    powerup_data = data.get('powerup_palettes', {})
    spiral_proj = pal_to_bytes(powerup_data.get('SpiralProjectile', {}).get('colors', ["0000", "7FE0", "5EC0", "3E80"]))
    shield_proj = pal_to_bytes(powerup_data.get('ShieldProjectile', {}).get('colors', ["0000", "03FF", "02BF", "019F"]))
    turbo_proj = pal_to_bytes(powerup_data.get('TurboProjectile', {}).get('colors', ["0000", "00FF", "00BF", "005F"]))

    return {
        'bg_data': bytes(bg_data),
        'obj_data': bytes(obj_data),
        'boss_palette_table': bytes(boss_palette_table),
        'boss_slot_table': bytes(boss_slot_table),
        'sara_witch_jet': sara_witch_jet,
        'sara_dragon_jet': sara_dragon_jet,
        'spiral_proj': spiral_proj,
        'shield_proj': shield_proj,
        'turbo_proj': turbo_proj,
    }


def create_tile_based_colorizer(colorizer_base_addr: int) -> bytes:
    """Optimized tile-based OBJ colorizer.

    v2.60 improvements:
    - Early skip for tile 0x00 (hidden sprites): saves ~188T per hidden sprite
    - Simplified comparison chain (fewer branches)
    - Removed first-4-sprites index heuristic (tiles map correctly without it)
    - ~30 of 40 sprites are typically hidden → saves ~11,280T per 2 buffers

    Registers: HL=flags ptr, D=Sara palette, E=boss slot, B=counter, C=temp
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

    emit([0x06, 0x28])  # LD B, 40
    labels['loop_start'] = len(code)

    # Read tile ID
    emit([0x2B])              # DEC HL          ; back to tile byte (offset 2)
    emit([0x7E])              # LD A, [HL]      ; A = tile_id
    emit([0x23])              # INC HL          ; back to flags byte (offset 3)

    # === FAST PATH: skip hidden sprites (tile 0x00) ===
    # ~30 of 40 sprites are hidden. This saves ~188T each.
    emit([0xB7])              # OR A            ; is tile 0x00?
    emit_jr(0x28, 'skip_sprite')  # JR Z, skip_sprite

    emit([0x4F])              # LD C, A         ; save tile in C

    # === TILE RANGE CLASSIFICATION ===
    emit([0xFE, 0x30])        # CP 0x30
    emit_jr(0x38, 'low_tiles')  # JR C, low_tiles  (tiles 0x01-0x2F)

    # === ENEMY TILES (0x30+) ===
    # Check boss override first
    emit([0x7B])              # LD A, E         ; boss palette slot
    emit([0xB7])              # OR A            ; any boss?
    emit_jr(0x20, 'boss_palette')  # JR NZ, boss_palette

    # Normal enemy palette by tile range
    emit([0x79])              # LD A, C         ; restore tile
    emit([0xFE, 0x40])        # CP 0x40
    emit_jr(0x38, 'pal_3')   # JR C, pal_3     (crows 0x30-0x3F)
    emit([0xFE, 0x50])        # CP 0x50
    emit_jr(0x38, 'pal_4')   # JR C, pal_4     (hornets 0x40-0x4F)
    emit([0xFE, 0x60])        # CP 0x60
    emit_jr(0x38, 'pal_5')   # JR C, pal_5     (orcs 0x50-0x5F)
    emit([0xFE, 0x70])        # CP 0x70
    emit_jr(0x38, 'pal_6')   # JR C, pal_6     (humanoids 0x60-0x6F)
    emit([0xFE, 0x80])        # CP 0x80
    emit_jr(0x38, 'pal_7')   # JR C, pal_7     (catfish 0x70-0x7F)
    emit([0x3E, 0x04])        # LD A, 0x04      ; fallback for >= 0x80
    emit_jr(0x18, 'apply_palette')

    # === LOW TILES (0x01-0x2F) ===
    labels['low_tiles'] = len(code)
    emit([0xFE, 0x20])        # CP 0x20
    emit_jr(0x30, 'sara_palette')  # JR NC, sara_palette (0x20-0x2F → Sara)
    emit([0xFE, 0x10])        # CP 0x10
    emit_jr(0x30, 'pal_4')   # JR NC, pal_4    (effects 0x10-0x1F)
    # Projectile tiles 0x01-0x0F
    emit([0xFE, 0x02])        # CP 0x02
    emit_jr(0x38, 'pal_3')   # JR C, pal_3     (enemy proj 0x01)
    emit([0xAF])              # XOR A           ; palette 0 (Sara projectiles)
    emit_jr(0x18, 'apply_palette')

    # === PALETTE ASSIGNMENTS ===
    labels['pal_3'] = len(code)
    emit([0x3E, 0x03])
    emit_jr(0x18, 'apply_palette')
    labels['pal_4'] = len(code)
    emit([0x3E, 0x04])
    emit_jr(0x18, 'apply_palette')
    labels['pal_5'] = len(code)
    emit([0x3E, 0x05])
    emit_jr(0x18, 'apply_palette')
    labels['pal_6'] = len(code)
    emit([0x3E, 0x06])
    emit_jr(0x18, 'apply_palette')
    labels['pal_7'] = len(code)
    emit([0x3E, 0x07])
    emit_jr(0x18, 'apply_palette')
    labels['sara_palette'] = len(code)
    emit(0x7A)                # LD A, D         ; Sara form palette
    emit_jr(0x18, 'apply_palette')
    labels['boss_palette'] = len(code)
    emit(0x7B)                # LD A, E         ; boss palette slot

    # === APPLY PALETTE ===
    labels['apply_palette'] = len(code)
    emit([0x4F])              # LD C, A         ; palette in C
    emit([0x7E])              # LD A, [HL]      ; read flags byte
    emit([0xE6, 0xF8])        # AND 0xF8        ; clear palette bits
    emit([0xB1])              # OR C            ; set new palette
    emit([0x77])              # LD [HL], A      ; write back

    # === ADVANCE TO NEXT SPRITE ===
    labels['skip_sprite'] = len(code)
    emit([0x23, 0x23, 0x23, 0x23])  # INC HL × 4 (advance to next sprite's flags)
    emit([0x05])              # DEC B
    loop_abs_addr = colorizer_base_addr + labels['loop_start']
    emit([0xC2, loop_abs_addr & 0xFF, (loop_abs_addr >> 8) & 0xFF])
    emit([0xC9])              # RET

    for offset_pos, target_label in forward_jumps:
        target = labels[target_label]
        offset = target - (offset_pos + 1)
        if offset < -128 or offset > 127:
            raise ValueError(f"Jump to {target_label} out of range: {offset}")
        code[offset_pos] = offset & 0xFF

    return bytes(code)


def create_shadow_colorizer_main(colorizer_addr: int, boss_slot_table_addr: int) -> bytes:
    """Shadow colorizer main - processes BOTH shadow OAM buffers."""
    code = bytearray()
    code.extend([0xF5, 0xC5, 0xD5, 0xE5])

    code.extend([0xF0, 0xBE, 0xB7, 0x20, 0x04])
    code.extend([0x16, 0x02, 0x18, 0x02])
    code.extend([0x16, 0x01])

    code.extend([0xF0, 0xBF])
    code.extend([0xB7])
    no_boss_jr_pos = len(code)
    code.extend([0x28, 0x00])
    code.extend([0x3D])
    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])
    code.extend([0x5E])
    done_boss_jr_pos = len(code)
    code.extend([0x18, 0x00])

    no_boss_pos = len(code)
    code[no_boss_jr_pos + 1] = no_boss_pos - (no_boss_jr_pos + 2)
    code.extend([0x1E, 0x00])

    done_boss_pos = len(code)
    code[done_boss_jr_pos + 1] = done_boss_pos - (done_boss_jr_pos + 2)

    code.extend([0x21, 0x03, 0xC0])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])
    code.extend([0x21, 0x03, 0xC1])
    code.extend([0xCD, colorizer_addr & 0xFF, colorizer_addr >> 8])

    code.extend([0xE1, 0xD1, 0xC1, 0xF1, 0xC9])
    return bytes(code)


def create_palette_loader(
    palette_data_addr: int,
    boss_palette_table_addr: int,
    boss_slot_table_addr: int,
    sara_witch_jet_addr: int,
    sara_dragon_jet_addr: int,
    spiral_proj_addr: int,
    shield_proj_addr: int,
    turbo_proj_addr: int,
) -> bytes:
    """Palette loader - unchanged from v2.33."""
    code = bytearray()

    code.extend([0xF0, 0xD0])
    code.append(0x57)

    code.extend([0x21, palette_data_addr & 0xFF, (palette_data_addr >> 8) & 0xFF])
    code.extend([0x3E, 0x80, 0xE0, 0x68, 0x0E, 0x40])
    code.extend([0x2A, 0xE0, 0x69, 0x0D, 0x20, 0xFA])

    obj_data_addr = palette_data_addr + 64
    code.extend([0x3E, 0x80, 0xE0, 0x6A])
    code.extend([0xF0, 0xC0])
    code.extend([0xB7])
    code.extend([0x28, 23])
    code.extend([0xFE, 0x01])
    code.extend([0x20, 0x05])
    code.extend([0x21, spiral_proj_addr & 0xFF, (spiral_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 17])
    code.extend([0xFE, 0x02])
    code.extend([0x20, 0x05])
    code.extend([0x21, shield_proj_addr & 0xFF, (shield_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 8])
    code.extend([0x21, turbo_proj_addr & 0xFF, (turbo_proj_addr >> 8) & 0xFF])
    code.extend([0x18, 3])
    code.extend([0x21, obj_data_addr & 0xFF, (obj_data_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0x88, 0xE0, 0x6A])
    sara_dragon_addr = obj_data_addr + 8
    code.extend([0x21, sara_dragon_addr & 0xFF, (sara_dragon_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_dragon_jet_addr & 0xFF, (sara_dragon_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0x90, 0xE0, 0x6A])
    sara_witch_addr = obj_data_addr + 16
    code.extend([0x21, sara_witch_addr & 0xFF, (sara_witch_addr >> 8) & 0xFF])
    code.extend([0x7A, 0xFE, 0x01, 0x20, 0x03])
    code.extend([0x21, sara_witch_jet_addr & 0xFF, (sara_witch_jet_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0x98, 0xE0, 0x6A])
    crow_addr = obj_data_addr + 24
    code.extend([0x21, crow_addr & 0xFF, (crow_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x18])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0xB0, 0xE0, 0x6A])
    humanoid_addr = obj_data_addr + 48
    code.extend([0x21, humanoid_addr & 0xFF, (humanoid_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0x3E, 0xB8, 0xE0, 0x6A])
    catfish_addr = obj_data_addr + 56
    code.extend([0x21, catfish_addr & 0xFF, (catfish_addr >> 8) & 0xFF])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    code.extend([0xF0, 0xBF])
    code.extend([0xB7])
    boss_skip_pos = len(code)
    code.extend([0x28, 0x00])
    code.extend([0x3D])
    code.extend([0x5F])
    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_slot_table_addr & 0xFF, (boss_slot_table_addr >> 8) & 0xFF])
    code.extend([0x09])
    code.extend([0x7E])
    code.extend([0x87])
    code.extend([0xF6, 0x80])
    code.extend([0xE0, 0x6A])
    code.extend([0x7B])
    code.extend([0x87, 0x87, 0x87])
    code.extend([0x4F])
    code.extend([0x06, 0x00])
    code.extend([0x21, boss_palette_table_addr & 0xFF, (boss_palette_table_addr >> 8) & 0xFF])
    code.extend([0x09])
    code.extend([0x0E, 0x08])
    code.extend([0x2A, 0xE0, 0x6B, 0x0D, 0x20, 0xFA])

    no_boss_pos = len(code)
    code[boss_skip_pos + 1] = no_boss_pos - (boss_skip_pos + 2)
    code.append(0xC9)
    return bytes(code)


def create_conditional_palette(palette_loader_addr: int) -> bytes:
    """Conditional palette wrapper - only calls palette loader when game state changes.

    Hashes FFBE^FFBF^FFC0^FFD0, compares with cached value in FFA9.
    If unchanged, returns immediately (~116T). If changed, updates cache
    and tail-calls the palette loader (~4,984T but rare).

    INC A at the end ensures hash(0,0,0,0) = 1, which won't match the
    initial FFA9 value of 0x00, guaranteeing palette load on first gameplay frame.
    """
    code = bytearray()

    # Compute hash of 4 game state bytes
    code.extend([0xF0, 0xBE])        # LDH A, [FFBE]     ; Sara form       (12T)
    code.extend([0x47])              # LD B, A                              (4T)
    code.extend([0xF0, 0xBF])        # LDH A, [FFBF]     ; Boss flag       (12T)
    code.extend([0xA8])              # XOR B                                (4T)
    code.extend([0x47])              # LD B, A                              (4T)
    code.extend([0xF0, 0xC0])        # LDH A, [FFC0]     ; Powerup state   (12T)
    code.extend([0xA8])              # XOR B                                (4T)
    code.extend([0x47])              # LD B, A                              (4T)
    code.extend([0xF0, 0xD0])        # LDH A, [FFD0]     ; Stage flag      (12T)
    code.extend([0xA8])              # XOR B                                (4T)
    code.extend([0x3C])              # INC A              ; offset so 0→1   (4T)

    # Compare with cached hash
    code.extend([0x47])              # LD B, A            ; save new hash   (4T)
    code.extend([0xF0, 0xA9])        # LDH A, [FFA9]     ; cached hash     (12T)
    code.extend([0xB8])              # CP B               ; compare         (4T)
    code.extend([0xC8])              # RET Z              ; skip if same    (20T taken / 8T not)

    # State changed - update cache and tail-call palette loader
    code.extend([0x78])              # LD A, B            ; restore hash    (4T)
    code.extend([0xE0, 0xA9])        # LDH [FFA9], A     ; update cache    (12T)
    code.extend([0xC3, palette_loader_addr & 0xFF, palette_loader_addr >> 8])
                                     # JP palette_loader  ; tail call       (16T)

    return bytes(code)


def create_tile_to_palette_subroutine() -> bytes:
    """Tile->palette subroutine for OBJ colorizer (CALL-based).

    Input: A = tile ID
    Output: A = palette number (0, 1, 6) or 0xFF = skip marker
    """
    code = bytearray()
    code.extend([0xFE, 0xFF])   # CP 0xFF
    code.extend([0xC8])         # RET Z
    cp1 = len(code); code.extend([0xFE, 0x05, 0x38, 0x00])
    cp2 = len(code); code.extend([0xFE, 0x07, 0x38, 0x00])
    cp3 = len(code); code.extend([0xFE, 0x13, 0x38, 0x00])
    cp4 = len(code); code.extend([0xFE, 0x60, 0x38, 0x00])
    cp5 = len(code); code.extend([0xFE, 0x88, 0x38, 0x00])
    cp6 = len(code); code.extend([0xFE, 0xE0, 0x38, 0x00])
    cp7 = len(code); code.extend([0xFE, 0xFE, 0x38, 0x00])
    pal0 = len(code); code.extend([0xAF, 0xC9])
    pal1 = len(code); code.extend([0x3E, 0x01, 0xC9])
    pal6 = len(code); code.extend([0x3E, 0x06, 0xC9])
    code[cp1 + 3] = (pal0 - (cp1 + 4)) & 0xFF
    code[cp2 + 3] = (pal6 - (cp2 + 4)) & 0xFF
    code[cp3 + 3] = (pal0 - (cp3 + 4)) & 0xFF
    code[cp4 + 3] = (pal6 - (cp4 + 4)) & 0xFF
    code[cp5 + 3] = (pal0 - (cp5 + 4)) & 0xFF
    code[cp6 + 3] = (pal1 - (cp6 + 4)) & 0xFF
    code[cp7 + 3] = (pal6 - (cp7 + 4)) & 0xFF
    return bytes(code)


def create_bg_tile_table() -> bytes:
    """256-byte ROM lookup table: tile_id -> BG palette number.

    Tile 0xFF maps to 0xFF (skip marker) for the anti-flicker filter.
    During PPU mode 3, VRAM reads return 0xFF → lookup returns 0xFF →
    caller skips the write → existing correct palette preserved.
    """
    table = bytearray(256)
    for tile in range(256):
        if tile == 0xFF:
            table[tile] = 0xFF  # skip marker (anti-flicker)
        elif tile < 0x05:
            table[tile] = 0     # floor checkerboard
        elif tile < 0x07:
            table[tile] = 6     # platform corners
        elif tile < 0x13:
            table[tile] = 0     # floor edges
        elif tile < 0x60:
            table[tile] = 6     # structural + platforms + walls
        elif tile < 0x88:
            table[tile] = 0     # arch/doorway/UI
        elif tile < 0xE0:
            table[tile] = 1     # items (gold)
        elif tile < 0xFE:
            table[tile] = 6     # decorative/structural
        else:
            table[tile] = 0     # void (0xFE)
    return bytes(table)


def create_bg_colorizer(bg_table_addr: int) -> bytes:
    """BG colorizer: High-speed sweep with 0xFF anti-flicker filter.

    MiSTer-optimized: NO STAT waits. Accepts that VRAM reads during mode 3
    return 0xFF. The ROM lookup table maps 0xFF → 0xFF (skip marker).
    When the caller sees 0xFF, it skips the VBK switch + write entirely,
    so existing correct palettes are NEVER damaged by bad reads.

    Accuracy monotonically increases: tiles only get better, never worse.
    157 tiles/frame = 1024/157 = 6.5 frames (0.11s) per full sweep.

    Safe HRAM: FF91=counter_lo, FFA5=counter_hi
    """
    TILES_PER_VBLANK = 157  # prime, coprime with 1024
    # 157 no-STAT tiles at ~100T avg = ~15,700T BG + ~8,500T OBJ = ~34.5% of frame
    # Sweep: 1024/157 = 6.5 frames = 0.11s (44% faster than v2.61's 0.16s)

    bg_table_hi = (bg_table_addr >> 8) & 0xFF

    code = bytearray()
    forward_jumps = []
    labels = {}

    def emit(opcodes):
        code.extend(opcodes if isinstance(opcodes, (list, bytes, bytearray)) else [opcodes])

    def emit_jr(opcode, target_label):
        """Emit JR with forward reference to be patched later."""
        code.append(opcode)
        forward_jumps.append((len(code), target_label))
        code.append(0x00)  # placeholder

    # === CHECK GAME MODE ===
    emit([0xF0, 0xC1])        # LDH A, [FFC1]
    emit([0xB7])              # OR A
    emit([0xC8])              # RET Z (skip on menus)

    emit([0xC5, 0xD5, 0xE5])  # PUSH BC, DE, HL

    # === COMPUTE ADDRESS: counter + LCDC tilemap base ===
    emit([0xF0, 0xA5])        # LDH A, [FFA5]     ; counter high (0-3)
    emit([0xE6, 0x03])        # AND 0x03
    emit([0xC6, 0x98])        # ADD A, 0x98        ; D = 0x98-0x9B (base)
    emit([0x57])              # LD D, A
    emit([0xF0, 0x40])        # LDH A, [FF40]     ; LCDC
    emit([0xE6, 0x08])        # AND 0x08           ; bit 3 → 0 or 8
    emit([0x0F])              # RRCA               ; → 0 or 4
    emit([0x82])              # ADD A, D           ; D = 0x98-0x9B or 0x9C-0x9F
    emit([0x57])              # LD D, A
    emit([0xF0, 0x91])        # LDH A, [FF91]     ; counter low
    emit([0x5F])              # LD E, A

    # Set tile count and table pointer
    emit([0x06, TILES_PER_VBLANK])  # LD B, tiles_per_vblank
    emit([0x26, bg_table_hi])  # LD H, table_hi

    # Ensure VRAM bank 0
    emit([0xAF])              # XOR A
    emit([0xE0, 0x4F])        # LDH [FF4F], A

    # === SWEEP LOOP ===
    labels['sweep_loop'] = len(code)

    # Read tile (VBK=0) - may return 0xFF during mode 3
    emit([0x1A])              # LD A, [DE]          ; 8T  VRAM read
    emit([0x6F])              # LD L, A             ; 4T  lookup index
    emit([0x7E])              # LD A, [HL]          ; 8T  ROM table → palette (or 0xFF)

    # 0xFF anti-flicker filter: skip write if lookup returned 0xFF
    emit([0x3C])              # INC A               ; 4T  (0xFF → 0x00, sets Z)
    emit_jr(0x28, 'skip_write')  # JR Z, skip_write ; 12T taken / 8T not
    emit([0x3D])              # DEC A               ; 4T  restore palette value

    # Write attr (VBK=1) - may fail during mode 3, but that's OK
    # (failed write = tile keeps old palette = no damage)
    emit([0x4F])              # LD C, A             ; 4T  save palette
    emit([0x3E, 0x01])        # LD A, 0x01          ; 8T
    emit([0xE0, 0x4F])        # LDH [FF4F], A       ; 12T  VBK = 1
    emit([0x79])              # LD A, C             ; 4T  restore palette
    emit([0x12])              # LD [DE], A           ; 8T  VRAM write
    emit([0xAF])              # XOR A               ; 4T
    emit([0xE0, 0x4F])        # LDH [FF4F], A       ; 12T  VBK = 0

    labels['skip_write'] = len(code)

    # === Advance counter (INC E only, manual D wrap) ===
    emit([0x1C])              # INC E               ; 4T (vs INC DE = 8T)
    emit_jr(0x20, 'no_wrap')  # JR NZ, no_wrap      ; 12T taken (99.6%)

    # Wrap: E went 0xFF→0x00, recompute D with tilemap offset
    emit([0x14])              # INC D
    emit([0x7A])              # LD A, D
    emit([0xE6, 0x03])        # AND 0x03            ; strip to 0-3
    emit([0xC6, 0x98])        # ADD A, 0x98         ; base 0x98-0x9B
    emit([0x57])              # LD D, A
    emit([0xF0, 0x40])        # LDH A, [FF40]      ; LCDC bit 3
    emit([0xE6, 0x08])        # AND 0x08
    emit([0x0F])              # RRCA                ; 0 or 4
    emit([0x82])              # ADD A, D            ; + tilemap offset
    emit([0x57])              # LD D, A

    labels['no_wrap'] = len(code)

    # === Loop back ===
    emit([0x05])              # DEC B
    sweep_end = len(code)
    sweep_target = labels['sweep_loop']
    sweep_offset = sweep_target - (sweep_end + 2)
    if sweep_offset < -128 or sweep_offset > 127:
        raise ValueError(f"Sweep loop JR NZ offset {sweep_offset} out of range!")
    emit([0x20, sweep_offset & 0xFF])  # JR NZ, sweep_loop

    # === SAVE COUNTER (AND 0x03 strips tilemap offset) ===
    emit([0x7A])              # LD A, D
    emit([0xE6, 0x03])        # AND 0x03            ; counter_high (0-3)
    emit([0xE0, 0xA5])        # LDH [FFA5], A
    emit([0x7B])              # LD A, E
    emit([0xE0, 0x91])        # LDH [FF91], A

    # === CLEANUP ===
    emit([0xAF])              # XOR A
    emit([0xE0, 0x4F])        # LDH [FF4F], A      ; VBK = 0

    emit([0xE1, 0xD1, 0xC1])  # POP HL, DE, BC
    emit([0xC9])              # RET

    # === PATCH FORWARD JUMPS ===
    for offset_pos, target_label in forward_jumps:
        target = labels[target_label]
        offset = target - (offset_pos + 1)
        if offset < -128 or offset > 127:
            raise ValueError(f"JR to {target_label} out of range: {offset}")
        code[offset_pos] = offset & 0xFF

    return bytes(code)


def create_combined_with_dma(conditional_palette_addr: int, shadow_main_addr: int, bg_colorizer_addr: int) -> bytes:
    """Combined: BG -> ConditionalPalette -> OBJ -> DMA.

    ConditionalPalette checks hash of FFBE/FFBF/FFC0/FFD0 and only calls
    the palette loader when state changes. Saves ~4,700T on most frames.
    """
    code = bytearray()
    code.extend([0xCD, bg_colorizer_addr & 0xFF, bg_colorizer_addr >> 8])
    code.extend([0xCD, conditional_palette_addr & 0xFF, conditional_palette_addr >> 8])
    code.extend([0xCD, shadow_main_addr & 0xFF, shadow_main_addr >> 8])
    code.extend([0xCD, 0x80, 0xFF, 0xC9])
    return bytes(code)


def create_vblank_hook_with_input(combined_func_addr: int) -> bytes:
    """VBlank hook - v2.36 STABLE style.

    1 d-pad read + 8 button reads (loop) + explicit bank restore.
    This is the EXACT hook from v2.36 which had zero ship mode issues.
    """
    lo = combined_func_addr & 0xFF
    hi = (combined_func_addr >> 8) & 0xFF

    joypad_input = bytearray([
        # D-pad (1 read - d-pad matrix settles fast)
        0x3E, 0x20,        # LD A, 0x20        ; select d-pad
        0xE0, 0x00,        # LDH [FF00], A
        0xF0, 0x00,        # LDH A, [FF00]     ; read d-pad
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xCB, 0x37,        # SWAP A            ; d-pad to upper nibble
        0x47,              # LD B, A            ; save in B
        # Buttons (8 reads via loop)
        0x3E, 0x10,        # LD A, 0x10        ; select buttons
        0xE0, 0x00,        # LDH [FF00], A
        0x0E, 0x08,        # LD C, 8           ; read 8 times
        0xF0, 0x00,        # .loop: LDH A,[FF00]
        0x0D,              # DEC C
        0x20, 0xFB,        # JR NZ, .loop
        0x2F,              # CPL
        0xE6, 0x0F,        # AND 0x0F
        0xB0,              # OR B              ; combine
        0xE0, 0x93,        # LDH [FF93], A
        # Deselect joypad
        0x3E, 0x30,        # LD A, 0x30
        0xE0, 0x00,        # LDH [FF00], A
    ])  # 33 bytes

    hook_code = bytearray([
        0x3E, 0x0D,              # LD A, 0x0D       ; bank 13
        0xEA, 0x00, 0x20,        # LD [0x2000], A
        0xCD, lo, hi,            # CALL combined
        0x3E, 0x01,              # LD A, 0x01       ; bank 1 (explicit)
        0xEA, 0x00, 0x20,        # LD [0x2000], A
        0xC9,                    # RET
    ])  # 14 bytes

    total = joypad_input + hook_code
    assert len(total) == 47, f"Hook is {len(total)} bytes, must be exactly 47!"
    return bytes(total)


def main():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_rom = Path("rom/working/penta_dragon_dx_FIXED.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    print("=== Penta Dragon DX v2.63 ===")
    print("High-speed BG sweep + 0xFF anti-flicker filter + no STAT waits (MiSTer-optimized)")
    print()

    with open(input_rom, "rb") as f:
        rom = bytearray(f.read())

    apply_all_display_patches(rom)

    palettes = load_palettes_from_yaml(palette_yaml)

    # === DATA LAYOUT (Bank 13) ===
    palette_data_addr = 0x6800
    boss_palette_table_addr = 0x6880
    boss_slot_table_addr = 0x68C0
    sara_witch_jet_addr = 0x68D0
    sara_dragon_jet_addr = 0x68D8
    spiral_proj_addr = 0x68E0
    shield_proj_addr = 0x68E8
    turbo_proj_addr = 0x68F0

    # === CODE LAYOUT (Bank 13) ===
    palette_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_to_pal_addr = 0x6B00  # subroutine for OBJ colorizer
    bg_colorizer_addr = 0x6C00
    cond_palette_addr = 0x6C80  # NEW: conditional palette wrapper
    combined_addr = 0x6D00
    bg_table_addr = 0x6E00     # 256-byte ROM lookup table for BG

    # Generate code
    palette_loader = create_palette_loader(
        palette_data_addr, boss_palette_table_addr, boss_slot_table_addr,
        sara_witch_jet_addr, sara_dragon_jet_addr,
        spiral_proj_addr, shield_proj_addr, turbo_proj_addr,
    )
    cond_palette = create_conditional_palette(palette_loader_addr)
    shadow_main = create_shadow_colorizer_main(colorizer_addr, boss_slot_table_addr)
    colorizer = create_tile_based_colorizer(colorizer_addr)
    tile_to_pal = create_tile_to_palette_subroutine()
    bg_table = create_bg_tile_table()
    bg_colorizer = create_bg_colorizer(bg_table_addr)
    combined = create_combined_with_dma(cond_palette_addr, shadow_main_addr, bg_colorizer_addr)
    vblank_hook = create_vblank_hook_with_input(combined_addr)

    # Print sizes
    print(f"Palette loader: {len(palette_loader)} bytes at 0x{palette_loader_addr:04X}")
    print(f"Cond. palette:  {len(cond_palette)} bytes at 0x{cond_palette_addr:04X}")
    print(f"Shadow main: {len(shadow_main)} bytes at 0x{shadow_main_addr:04X}")
    print(f"OBJ colorizer: {len(colorizer)} bytes at 0x{colorizer_addr:04X}")
    print(f"Tile->pal sub: {len(tile_to_pal)} bytes at 0x{tile_to_pal_addr:04X}")
    print(f"BG colorizer: {len(bg_colorizer)} bytes at 0x{bg_colorizer_addr:04X}")
    print(f"BG tile table: {len(bg_table)} bytes at 0x{bg_table_addr:04X}")
    print(f"Combined: {len(combined)} bytes at 0x{combined_addr:04X}")
    print(f"VBlank hook: {len(vblank_hook)} bytes at 0x0824")
    print(f"Palette savings: ~4,728 T-cycles/frame (skipped on 95%+ of frames)")

    # Verify no overlaps
    regions = [
        ('palette_loader', palette_loader_addr, len(palette_loader)),
        ('cond_palette', cond_palette_addr, len(cond_palette)),
        ('shadow_main', shadow_main_addr, len(shadow_main)),
        ('colorizer', colorizer_addr, len(colorizer)),
        ('tile_to_pal', tile_to_pal_addr, len(tile_to_pal)),
        ('bg_colorizer', bg_colorizer_addr, len(bg_colorizer)),
        ('combined', combined_addr, len(combined)),
        ('bg_table', bg_table_addr, len(bg_table)),
    ]
    for i, (name_a, start_a, size_a) in enumerate(regions):
        for name_b, start_b, size_b in regions[i + 1:]:
            end_a = start_a + size_a
            end_b = start_b + size_b
            if start_a < end_b and start_b < end_a:
                raise ValueError(f"OVERLAP: {name_a} (0x{start_a:04X}-0x{end_a:04X}) "
                                 f"and {name_b} (0x{start_b:04X}-0x{end_b:04X})")

    bank13_offset = 13 * 0x4000
    max_addr = 0x4000 + 0x4000  # Bank 13 ends at 0x7FFF

    def write_bank13(addr, data):
        if addr + len(data) > max_addr:
            raise ValueError(f"Data at 0x{addr:04X} extends past bank 13 boundary!")
        rom_offset = bank13_offset + (addr - 0x4000)
        rom[rom_offset:rom_offset + len(data)] = data

    # Write palette data
    write_bank13(palette_data_addr, palettes['bg_data'])
    write_bank13(palette_data_addr + 64, palettes['obj_data'])
    write_bank13(boss_palette_table_addr, palettes['boss_palette_table'])
    write_bank13(boss_slot_table_addr, palettes['boss_slot_table'])
    write_bank13(sara_witch_jet_addr, palettes['sara_witch_jet'])
    write_bank13(sara_dragon_jet_addr, palettes['sara_dragon_jet'])
    write_bank13(spiral_proj_addr, palettes['spiral_proj'])
    write_bank13(shield_proj_addr, palettes['shield_proj'])
    write_bank13(turbo_proj_addr, palettes['turbo_proj'])

    # Write code
    write_bank13(palette_loader_addr, palette_loader)
    write_bank13(cond_palette_addr, cond_palette)
    write_bank13(shadow_main_addr, shadow_main)
    write_bank13(colorizer_addr, colorizer)
    write_bank13(tile_to_pal_addr, tile_to_pal)
    write_bank13(bg_colorizer_addr, bg_colorizer)
    write_bank13(bg_table_addr, bg_table)
    write_bank13(combined_addr, combined)

    # Patch ROM hooks
    rom[0x06D5:0x06D5 + 3] = bytearray([0x00, 0x00, 0x00])
    rom[0x0824:0x0824 + len(vblank_hook)] = vblank_hook

    rom[0x143] = 0x80

    # Fix header checksum (required by PyBoy and some strict emulators)
    x = 0
    for i in range(0x134, 0x14D):
        x = (x - rom[i] - 1) & 0xFF
    rom[0x14D] = x
    print(f"\nSet CGB flag at 0x143, header checksum 0x{x:02X}")

    output_rom.parent.mkdir(parents=True, exist_ok=True)
    with open(output_rom, "wb") as f:
        f.write(rom)

    print(f"\nROM patched successfully -> {output_rom}")
    print(f"Total bank 13 usage: 0x6800-0x{bg_table_addr + len(bg_table) - 1:04X} "
          f"({bg_table_addr + len(bg_table) - 0x6800} bytes)")


if __name__ == "__main__":
    main()
