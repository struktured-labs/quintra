# Projectile Tile Mapping - v2.32

## Overview

This document maps projectile tile IDs to their sources for implementing per-entity projectile colorization.

**Status**: VERIFIED (Phase 1 Research Complete)
Data collected via MCP OAM dumps from multiple save states.

## Key Finding: Tiles ARE Distinct Per Source

Sara W and Sara D use **different tile IDs** for their projectiles, enabling tile-based colorization without dynamic palette hacks.

## Verified Projectile Tile Assignments

| Tile ID | Source | Description | Recommended Palette |
|---------|--------|-------------|---------------------|
| 0x00 | Enemy/Boss | Generic enemy projectile (gargoyle) | 3 (dark blue) |
| 0x01 | Spider boss | Spider boss projectile | 7 (boss red/orange) |
| 0x02-0x05 | Unknown | Unverified | 0 (default) |
| **0x06** | **Sara D** | Dragon fire projectile | **1 (green)** |
| 0x07-0x08 | Unknown | Unverified | 0 (default) |
| **0x09** | **Sara D** | Dragon fire projectile | **1 (green)** |
| **0x0A** | **Sara D** | Dragon fire projectile | **1 (green)** |
| 0x0B-0x0E | Unknown | Unverified | 0 (default) |
| **0x0F** | **Sara W** | Witch magic projectile (round) | **2 (pink)** |
| 0x10-0x1F | Effects | Death animations, impacts, etc. | 4 (yellow/white) |

## Detailed Findings by Save State

### Sara W + Orc (level1_sara_w_orc.ss0)
- **tile 0x0F**: Sara W projectile (flags 0x00 = Palette 0)
- Count: 47 instances over 300 frames
- Consistent single tile for all Sara W shots

### Sara W + 4 Hornets (level1_sara_w_4_hornets.ss0)
- **tile 0x0F**: Sara W projectile (flags 0x00 = Palette 0)
- Count: 41 instances over 300 frames
- Effect tiles observed: 0x12-0x1D (death animations)

### Sara D Firing (level1_sara_d_alone.ss0 + A button)
- **tile 0x06**: Dragon fire (flags 0x00, 0x40) - count 15
- **tile 0x09**: Dragon fire (flags 0x00, 0x40) - count 26
- **tile 0x0A**: Dragon fire (flags 0x00, 0x40) - count 26
- Flag 0x40 = X-flip for directional sprites
- Sara D uses 3 different tiles (multi-part breath attack)

### Spider Boss (v2.26_level1_sara_w_spider_mini_boss.ss0)
- **tile 0x01**: Spider projectile (flags 0x00 = Palette 0)
- Count: 66 instances (stationary at 132,84)
- **tile 0x1D**: UI element with flags 0x07 (Palette 7)

### Gargoyle Boss (level1_sara_w_gargoyle_mini_boss.ss0)
- Boss body uses tiles 0x30-0x7F (Palette 6)
- **tile 0x00**: Appears with flags 0x00 (possible projectile)
- Tiles 0x6E, 0x6F, 0x7C, 0x7F have flip flags (animated boss parts)

## Effect Tiles (0x10-0x1F)

| Tile | Purpose | Observations |
|------|---------|--------------|
| 0x12-0x15 | Death/hit effects | 2x2 sprite pattern |
| 0x16-0x19 | Death animation frame 2 | |
| 0x1A-0x1D | Death animation frame 3 | UI element uses 0x1D |

## Memory Addresses (Verified)

| Address | Purpose | Values |
|---------|---------|--------|
| **0xFFBE** | Sara form | 0=Witch, non-zero=Dragon |
| **0xFFBF** | Boss flag | 0=normal, 1=Gargoyle, 2=Spider |
| **0xFFC0** | Powerup flag | 0=none, 1=spiral, 2=shield |
| **0xFFD0** | Stage flag | 0=Level 1, 1=Bonus stage |

### Powerup Flag Values (0xFFC0)
- **0x00**: No powerup / baseline
- **0x01**: Spiral weapon active
- **0x02**: Shield active
- Other powerups: TBD (turbo showed 0x00, may use different address)

## Implementation for v2.32

### Tile Colorizer Logic

```asm
; Projectile/effect range (tiles 0x00-0x1F)
check_projectile_range:
    LD A, C             ; Get tile ID
    CP 0x20             ; Is it < 0x20?
    JR NC, check_sara   ; No, continue to Sara check

    ; Check specific Sara projectile tiles
    CP 0x0F             ; Sara W projectile?
    JR Z, sara_w_projectile

    CP 0x06             ; Sara D tile 0x06?
    JR Z, sara_d_projectile
    CP 0x09             ; Sara D tile 0x09?
    JR Z, sara_d_projectile
    CP 0x0A             ; Sara D tile 0x0A?
    JR Z, sara_d_projectile

    CP 0x02             ; Boss/enemy projectile range (0x00-0x01)?
    JR C, enemy_projectile

    CP 0x10             ; Effect range (0x10-0x1F)?
    JR NC, effect_tile

    ; Unknown tiles 0x02-0x05, 0x07-0x08, 0x0B-0x0E
    XOR A               ; Default Palette 0
    JR apply_palette

sara_w_projectile:
    LD A, 2             ; Palette 2 (pink - Sara W colors)
    JR apply_palette

sara_d_projectile:
    LD A, 1             ; Palette 1 (green - Sara D colors)
    JR apply_palette

enemy_projectile:
    LD A, 3             ; Palette 3 (dark blue)
    JR apply_palette

effect_tile:
    LD A, 4             ; Palette 4 (yellow/white effects)
    JR apply_palette
```

### Alternative: Powerup-Based Palette Loading

For powerup-colored projectiles, modify palette loader:

```asm
load_projectile_palettes:
    ; Check powerup state
    LDH A, [0xFFC0]     ; Read powerup flag
    OR A
    JR Z, load_form_based

    CP 0x01             ; Spiral?
    JR NZ, check_shield
    ; Load cyan into Palette 0 for spiral
    LD HL, spiral_palette_data
    JR load_palette_0

check_shield:
    CP 0x02             ; Shield?
    JR NZ, load_form_based
    ; Load gold into Palette 0 for shield
    LD HL, shield_palette_data
    JR load_palette_0

load_form_based:
    ; Fall back to Sara form-based colors
    LDH A, [0xFFBE]
    OR A
    JR NZ, load_dragon_colors
    ; Sara W colors
    LD HL, sara_w_projectile_data
    JR load_palette_0

load_dragon_colors:
    LD HL, sara_d_projectile_data
    ; Fall through to load_palette_0
```

## Palette Color Recommendations

### Projectile Palettes
| Palette | Use | Colors (GBC format) |
|---------|-----|---------------------|
| 0 | Dynamic/powerup | Varies by powerup state |
| 1 | Sara D projectile | Trans, bright green, dark green, black |
| 2 | Sara W projectile | Trans, pink, magenta, dark red |
| 3 | Enemy projectile | Trans, dark blue, navy, black |

### Powerup-Specific Colors
| Powerup | Palette 0 Colors | Visual |
|---------|------------------|--------|
| Spiral (0x01) | Cyan, light blue, dark blue | Rotating cyan bullets |
| Shield (0x02) | Gold, yellow, orange | Golden shield glow |
| Turbo | Orange, red, dark red | Speed trails |

## Testing Commands

```bash
# Verify Sara W projectile (tile 0x0F)
mcp__mgba__mgba_dump_oam(
    rom_path="rom/working/penta_dragon_dx_FIXED.gb",
    savestate_path="save_states_for_claude/level1_sara_w_orc.ss0",
    frames=120
)

# Verify Sara D projectiles (tiles 0x06, 0x09, 0x0A)
mcp__mgba__mgba_run_lua(
    rom_path="rom/working/penta_dragon_dx_FIXED.gb",
    savestate_path="save_states_for_claude/level1_sara_d_alone.ss0",
    script="-- Press A and track tiles",
    timeout=60
)

# Verify powerup flag
mcp__mgba__mgba_read_range(
    rom_path="rom/working/penta_dragon_dx_FIXED.gb",
    savestate_path="save_states_for_claude/sara_w_special_spiral_weapon_activated_level1_v_2.31.ss0",
    start_address=0xFFC0,
    length=4,
    frames=30
)
```

## Version History

- **v2.29**: Initial projectile sub-range implementation (BROKEN)
- **v2.30**: Jump offset fix attempt (BROKEN)
- **v2.31**: Dynamic Palette 0 based on Sara form (STABLE)
- **v2.32**: Per-entity projectile tiles + powerup support (IN DEVELOPMENT)

## Files Modified

- `scripts/create_vblank_colorizer_v232.py` - New implementation
- `palettes/penta_palettes_v097.yaml` - Projectile palettes added
- `docs/projectile_tile_mapping.md` - This document (updated)
