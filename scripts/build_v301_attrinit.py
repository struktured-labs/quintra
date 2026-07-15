#!/usr/bin/env python3
"""Penta Dragon DX v3.01 — DIAGNOSTIC variant: cold-boot VRAM bank-1 attr
init.

Identical to `build_v301_gdma.py` (which produces production
`rom/working/penta_dragon_dx_v301.gb`) except for a single addition:

  ATTR CLEANER. On cold boot (first VBlank — when DF02 != 0x5A sentinel),
  schedules a 32-frame, incremental clear of VRAM bank-1 attributes for
  both displayed and non-displayed tilemap regions (0x9800..0x9FFF). One
  row of 64 bytes total per frame (32 in 0x9800 region + 32 in 0x9C00
  region) keeps each frame's VBlank cost tiny (~500 T-cycles), well under
  the budget that previously caused palette-load CRAM-write drops
  (see docs/v301_resolved_issues.md, Issue: White splotches).

ROOT CAUSE BEING DIAGNOSED:
  VRAM bank 1 (CGB tilemap attributes) holds 0xFF after CGB boot ROM
  initialization. 0xFF means "use BG palette 7" (high three bits of attr
  byte). The game's tile-write code at bank 1:0x42A7 is patched (v3.01)
  to also write attrs for tiles it touches — but only for tile positions
  it actually writes. Empty/unused tilemap positions retain 0xFF and
  render with whatever colors are in BG palette 7 (often blue/teal in
  the v3.01 palette set). Compounded with the inline-copy not running on
  every tile-write path (e.g., one-off splash tiles, window-layer tiles),
  this produces the "white/colored splotches" the user reports.

  By zeroing all attr bytes to 0x00 (palette 0 = default floor colors)
  at cold-boot, every tilemap position has a safe default palette before
  any game tile-write occurs. Subsequent tile writes still update attrs
  through the existing patch.

OUTPUT: rom/working/penta_dragon_dx_v301_attrinit.gb

NEW STATE BYTE:
  DF07 — row counter for the cold-boot attr cleaner.
         Initialized to 32 in cold-boot branch.
         Decremented and used as row index in warm-path attr cleaner.
         Reaches 0 after 32 frames → cleaner becomes a 12T no-op.

THIS DOES NOT TOUCH the warm-path colorize handler hot section
(palette_loader, bg_sweep, OBJ colorizer, OAM DMA, inline tile+attr
copy at 0x42A7) — all of those remain byte-for-byte identical to v3.01
production.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bg_experiment import (
    load_palettes_from_yaml, create_tile_based_colorizer,
    create_shadow_colorizer_main, create_palette_loader,
    create_tile_to_palette_subroutine,
)
from create_vblank_colorizer_v288 import create_conditional_palette_cached
from build_v296_phantomsafe import create_bg_sweep_viewport_gated
from build_v301_gdma import (
    BG_TABLE_BYTES, WRAM_BG_TABLE, WRAM_BG_TABLE_HI, ATTR_BUFFER,
    create_inline_tile_copy_tileonly, create_gdma_transfer,
    create_attr_computation,
)


def _bg_table_no_ff_sentinel() -> bytes:
    """v3.01 bg_table with the pal-7 sentinel at index 0xFF cleared.

    PROBE FINDING 2026-05-23: production v3.01 bg_table has
    `table[0xFF] = 0xFF`. The inline tile+attr copy at 0x42A7 reads
    bg_table[tile_id] and writes it as the attr byte. When the game
    writes tile ID 0xFF (used as a blank/border tile in several places —
    menu bars, splash spacing, etc.), the corresponding attr becomes
    0xFF = pal 7 — producing colored splotches on title and STAGE 01
    splash where tile 0xFF tiles are placed.

    The probe shows: at f200 (after cold-boot cleaner finishes) BOTH
    tilemaps have 0 uninit attrs. By f400 (menu/splash phase), 97
    uninit attrs appear in 0x9800 — these came from tile-0xFF writes
    through the inline patch.

    Fix: change `table[0xFF] = 0` so tile-ID 0xFF → pal 0 (floor
    default). This eliminates the bg_table-introduced splotch source.

    Returns a copy of BG_TABLE_BYTES with byte 0xFF set to 0x00.
    """
    table = bytearray(BG_TABLE_BYTES)
    table[0xFF] = 0x00
    return bytes(table)


BG_TABLE_FIXED_BYTES = _bg_table_no_ff_sentinel()


def build_v301_attrinit():
    input_rom = Path("rom/Penta Dragon (J).gb")
    output_path = Path("rom/working/penta_dragon_dx_v301_attrinit.gb")
    palette_yaml = Path("palettes/penta_palettes_v097.yaml")

    rom = bytearray(input_rom.read_bytes())
    palettes = load_palettes_from_yaml(palette_yaml)

    # pal7 ← pal0 (hide stale CGB boot-ROM attrs) — still useful even with
    # the attr cleaner, because the cleaner takes 32 frames to complete;
    # tile positions written during the first 32 frames before their row
    # is cleared would still show pal 7 colors briefly.
    bg_data = bytearray(palettes['bg_data'])
    bg_data[56:64] = bg_data[0:8]
    palettes = {**palettes, 'bg_data': bytes(bg_data)}

    rom[0x143] = 0x80  # CGB flag

    # Bank 13 layout (identical to build_v301_gdma)
    bank13 = 13 * 0x4000
    pal_addr = 0x6800
    boss_pal_addr = 0x6880
    boss_slot_addr = 0x68C0
    swj_addr = 0x68D0; sdj_addr = 0x68D8
    sp_addr = 0x68E0; shp_addr = 0x68E8; tp_addr = 0x68F0
    pal_loader_addr = 0x6900
    shadow_main_addr = 0x69D0
    colorizer_addr = 0x6A10
    tile_pal_addr = 0x6B00
    cond_pal_addr = 0x6C90
    bg_sweep_addr = 0x6CD0
    gdma_addr = 0x6D80
    colorize_addr = 0x6E00
    bg_table_addr = 0x7000
    attr_comp_addr = 0x7100

    def w(addr, data):
        off = bank13 + (addr - 0x4000)
        rom[off:off + len(data)] = data

    # Palette data + tables (same as v3.00 / v3.01 production)
    w(pal_addr, palettes['bg_data'])
    w(pal_addr + 64, palettes['obj_data'])
    w(boss_pal_addr, palettes['boss_palette_table'])
    w(boss_slot_addr, palettes['boss_slot_table'])
    w(swj_addr, palettes['sara_witch_jet'])
    w(sdj_addr, palettes['sara_dragon_jet'])
    w(sp_addr, palettes['spiral_proj'])
    w(shp_addr, palettes['shield_proj'])
    w(tp_addr, palettes['turbo_proj'])

    w(pal_loader_addr, create_palette_loader(
        pal_addr, boss_pal_addr, boss_slot_addr,
        swj_addr, sdj_addr, sp_addr, shp_addr, tp_addr))
    w(shadow_main_addr, create_shadow_colorizer_main(colorizer_addr, boss_slot_addr))

    colorizer = bytearray(create_tile_based_colorizer(colorizer_addr))
    colorizer[1] = 0x0A
    w(colorizer_addr, bytes(colorizer))

    w(tile_pal_addr, create_tile_to_palette_subroutine())
    # NOTE: BG_TABLE_FIXED_BYTES differs from BG_TABLE_BYTES only at index 0xFF
    # (0xFF→0 instead of 0xFF→0xFF). See _bg_table_no_ff_sentinel for rationale.
    w(bg_table_addr, BG_TABLE_FIXED_BYTES)
    w(cond_pal_addr, create_conditional_palette_cached(pal_loader_addr))

    # bg_sweep safety net — identical to v3.01 production
    sweep = bytearray(create_bg_sweep_viewport_gated(bg_table_addr, bg_sweep_addr))
    assert sweep[:4] == bytearray([0xF0, 0xC1, 0xB7, 0xC8]), \
        f"bg_sweep prefix changed: {sweep[:4].hex()}"
    sweep[0:4] = bytearray([0x00, 0x00, 0x00, 0x00])
    w(bg_sweep_addr, bytes(sweep))

    # GDMA transfer routine (unused in warm path; kept for parity)
    gdma_code = create_gdma_transfer()
    assert gdma_addr + len(gdma_code) <= colorize_addr, \
        f"GDMA overflows: {gdma_addr + len(gdma_code):#X} > {colorize_addr:#X}"
    w(gdma_addr, gdma_code)
    print(f"  GDMA transfer: {len(gdma_code)} bytes at 0x{gdma_addr:04X}")

    # Attr computation routine (unused in warm path; kept for parity)
    attr_comp = create_attr_computation(bg_table_addr)
    w(attr_comp_addr, attr_comp)
    print(f"  attr computation: {len(attr_comp)} bytes at 0x{attr_comp_addr:04X}")

    # ============================================================
    # COLORIZE HANDLER — v3.01 production + ATTR CLEANER
    #
    # COLD-BOOT PATH IS IDENTICAL TO v3.01 PRODUCTION (byte-for-byte).
    # That is essential: any extra T-cycles on cold-boot push
    # palette_loader's first CRAM writes into LCD mode 2/3, causing
    # silent byte drops that result in wrong title-screen colors. See
    # docs/v301_resolved_issues.md (Issue: White splotches).
    #
    # Probe finding 2026-05-23: an earlier attrinit draft added the
    # DF07=32 init to the cold-boot path (5 bytes / 4 T-cycles).
    # That tiny extra cost was enough to corrupt BG palette 1 color 3
    # on the first frame (0x7FFF instead of 0x0000), making title
    # text invisible (white-on-yellow). The fix is to keep cold-boot
    # byte-for-byte identical and move the cleaner-init handshake into
    # the warm path AFTER cond_pal (where palette_loader has finished
    # its CRAM writes and any extra delay is harmless).
    #
    # NEW STATE BYTE: DF08 = cleaner-init sentinel (0x5A means initialized).
    # On first warm-path run, DF08 != 0x5A → set it + init DF07=32 +
    # skip cleaner body this frame. From the next frame onward, DF08
    # is 0x5A and the cleaner runs row 31, 30, ..., 0.
    #
    # ORDER inside warm path:
    #   cond_pal → cleaner (init handshake OR row clear) → FFC1 gate
    #
    # ON COLD-BOOT FRAME: same code path as production until skip_cold,
    #   then cond_pal (palette_loader forced — full VBlank for CRAM),
    #   then cleaner init handshake (sets DF08 + DF07=32, skips body),
    #   then FFC1 gate skipped (game not in play).
    # ON WARM FRAMES 2..33: skip cold → cond_pal (hash-gated) → cleaner
    #   runs row N → FFC1 gate.
    # ON WARM FRAMES 34+: skip cold → cond_pal → cleaner ~12T no-op →
    #   FFC1 gate. Steady state matches v3.01 production cost.
    # ============================================================
    code = bytearray()
    code.extend([0xF0, 0x4F, 0xF5])           # save VBK
    code.extend([0xAF, 0xE0, 0x4F])           # VBK = 0

    # DF02 magic byte cold-boot check
    code.extend([0xFA, 0x02, 0xDF, 0xFE, 0x5A])
    df02_jr = len(code) + 1
    code.extend([0x28, 0x00])                 # JR Z, skip_cold

    # ---- COLD-BOOT PATH (byte-for-byte identical to v3.01 production) ----
    code.extend([0x3E, 0x5A, 0xEA, 0x02, 0xDF])  # DF02 = 0x5A
    code.extend([0xAF, 0xEA, 0x00, 0xDF])         # DF00 = 0 (hash)

    # Copy bg_table ROM → WRAM 0xDA00 (256 bytes via B=0 loop)
    code.extend([0x21, bg_table_addr & 0xFF, (bg_table_addr >> 8) & 0xFF])
    code.extend([0x11, WRAM_BG_TABLE & 0xFF, (WRAM_BG_TABLE >> 8) & 0xFF])
    code.extend([0x06, 0x00])                 # B = 0 (256 iters)
    bg_copy = len(code)
    code.extend([0x2A, 0x12, 0x13, 0x05])    # [HL+]→[DE]; INC DE; DEC B
    offset = bg_copy - (len(code) + 2)
    code.extend([0x20, offset & 0xFF])

    # ---- skip_cold target ----
    code[df02_jr] = (len(code) - df02_jr - 1) & 0xFF

    # ---- WARM PATH ----
    # First call cond_pal (palette_loader if hash changed) BEFORE the
    # cleaner so CRAM writes land while LCD is reliably in mode 1.
    code.extend([0xCD, cond_pal_addr & 0xFF, (cond_pal_addr >> 8) & 0xFF])

    # ============================================================
    # ATTR CLEANER — clears one row (32 bytes) of attrs in BOTH
    # 0x9800 and 0x9C00 tilemap regions per frame. Runs at most 32
    # times total (then DF07=0 → fast skip). Total cost when active:
    # ~500 T-cycles; when idle: ~12 T-cycles.
    #
    # Why both regions: the game double-buffers between 0x9800 and
    # 0x9C00 via LCDC bit 3 (see docs/scroll_flicker_analysis.md).
    # Either tilemap can become displayed at any moment, so both must
    # have safe attrs from cold-boot. The inline tile+attr copy at
    # 0x42A7 only updates the currently-targeted tilemap per call.
    #
    # First-run handshake: DF08 != 0x5A → set DF08 + DF07=32, skip body.
    # This keeps cold-boot path byte-identical to production.
    #
    # Register usage: A, B, HL — all callee-saved by caller chain
    # already (handler's outer save/restore covers them).
    # ============================================================
    # First-run handshake: DF08 sentinel
    code.extend([0xFA, 0x08, 0xDF])           # LD A, [DF08]
    code.extend([0xFE, 0x5A])                 # CP 0x5A
    df08_jr = len(code) + 1
    code.extend([0x20, 0x00])                 # JR NZ, do_init  (forward)
    # already-initialized path: load DF07 to check counter
    code.extend([0xFA, 0x07, 0xDF])           # LD A, [DF07]
    code.extend([0xB7])                       # OR A
    cleaner_skip_jr = len(code) + 1
    code.extend([0x28, 0x00])                 # JR Z, skip_cleaner

    code.extend([0x3D])                       # DEC A
    code.extend([0xEA, 0x07, 0xDF])           # LD [DF07], A   (A = current row 0..31)

    # Compute HL = 0x9800 + (A << 5)
    code.extend([0x6F])                       # LD L, A
    code.extend([0x26, 0x00])                 # LD H, 0
    code.extend([0x29, 0x29, 0x29, 0x29, 0x29])  # ADD HL,HL × 5 (×32)
    code.extend([0x7C])                       # LD A, H
    code.extend([0xF6, 0x98])                 # OR 0x98
    code.extend([0x67])                       # LD H, A
    code.extend([0xE5])                       # PUSH HL  (save start addr for 0x9C00 pass)

    # VBK = 1
    code.extend([0x3E, 0x01, 0xE0, 0x4F])

    # Clear 32 bytes at HL (0x9800 + row*32)
    code.extend([0xAF])                       # XOR A (zero attr)
    code.extend([0x06, 0x20])                 # LD B, 32
    code.extend([0x22, 0x05, 0x20, 0xFC])     # loop: LD [HL+],A; DEC B; JR NZ,-4

    # Restore HL and switch to 0x9C00 region
    code.extend([0xE1])                       # POP HL
    code.extend([0x7C, 0xF6, 0x04, 0x67])     # LD A,H; OR 0x04; LD H,A   (0x98 → 0x9C)

    # Clear 32 bytes at HL (0x9C00 + row*32)
    code.extend([0xAF])                       # XOR A (loop's [HL+] needs A=0)
    code.extend([0x06, 0x20])                 # LD B, 32
    code.extend([0x22, 0x05, 0x20, 0xFC])     # loop: LD [HL+],A; DEC B; JR NZ,-4

    # VBK = 0
    code.extend([0xAF, 0xE0, 0x4F])

    # Skip over the init block below
    skip_init_jr = len(code) + 1
    code.extend([0x18, 0x00])                 # JR end_cleaner

    # do_init target (DF08 != 0x5A path)
    code[df08_jr] = (len(code) - df08_jr - 1) & 0xFF
    # Set DF08 = 0x5A, DF07 = 32. This frame skips cleaner body.
    code.extend([0x3E, 0x5A, 0xEA, 0x08, 0xDF])  # DF08 = 0x5A
    code.extend([0x3E, 0x20, 0xEA, 0x07, 0xDF])  # DF07 = 32

    # ---- skip_cleaner / end_cleaner targets ----
    code[skip_init_jr] = (len(code) - skip_init_jr - 1) & 0xFF
    code[cleaner_skip_jr] = (len(code) - cleaner_skip_jr - 1) & 0xFF

    code.extend([0xF0, 0xC1, 0xB7])
    ffc1_skip = len(code) + 1
    code.extend([0x28, 0x00])
    code.extend([0xCD, bg_sweep_addr & 0xFF, (bg_sweep_addr >> 8) & 0xFF])
    code.extend([0xCD, shadow_main_addr & 0xFF, (shadow_main_addr >> 8) & 0xFF])
    code.extend([0xCD, 0x80, 0xFF])           # OAM DMA
    code[ffc1_skip] = (len(code) - ffc1_skip - 1) & 0xFF

    code.extend([0xF1, 0xE0, 0x4F])           # POP AF; LDH [VBK], A
    code.extend([0xC9])

    assert colorize_addr + len(code) <= bg_table_addr, \
        f"colorize handler overflow: {colorize_addr + len(code):#X} > {bg_table_addr:#X}"
    w(colorize_addr, bytes(code))
    print(f"  colorize handler: {len(code)} bytes at 0x{colorize_addr:04X} "
          f"(+{len(code) - 57} vs v3.01 production)")

    # ============================================================
    # VBLANK HOOK at 0x0824 — identical to v3.01 production
    # ============================================================
    hook = bytearray([
        0xF0, 0x99, 0xF5,
        0x3E, 0x20, 0xE0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xCB, 0x37, 0x47,
        0x3E, 0x10, 0xE0, 0x00,
        0xF0, 0x00, 0xF0, 0x00,
        0x2F, 0xE6, 0x0F, 0xB0, 0xE0, 0x93,
        0x3E, 0x30, 0xE0, 0x00,
        0x3E, 0x0D, 0xEA, 0x00, 0x20,
        0xCD, colorize_addr & 0xFF, (colorize_addr >> 8) & 0xFF,
        0xF1, 0xEA, 0x00, 0x20,
        0xC9,
    ])
    assert len(hook) <= 47
    rom[0x0824:0x0824 + 47] = (hook + bytearray(47 - len(hook)))[:47]

    # NOP game DMA
    rom[0x06D5:0x06D8] = bytearray([0x00, 0x00, 0x00])

    # RST $38 RETI → RET
    rom[0x003B] = 0xC9

    # ============================================================
    # INLINE TILE-ONLY HOOK at bank1:0x42A7 — identical to v3.01 production
    # ============================================================
    inline_code = create_inline_tile_copy_tileonly()
    available = 0x436D - 0x42A7 + 1  # 199 bytes
    assert len(inline_code) <= available, \
        f"inline tile copy too big: {len(inline_code)} > {available}"

    rom[0x42A7:0x42A7 + len(inline_code)] = inline_code
    if len(inline_code) < available:
        rom[0x42A7 + len(inline_code):0x436E] = bytearray(available - len(inline_code))

    assert rom[0x42A0:0x42A7] == bytearray([0x26, 0x9C, 0xC3, 0xA7, 0x42, 0x26, 0x98])

    print(f"  inline tile copy: {len(inline_code)} bytes (tile-only, "
          f"{available - len(inline_code)} free)")

    # Header checksum
    chk = 0
    for b in rom[0x134:0x14D]:
        chk = (chk - b - 1) & 0xFF
    rom[0x14D] = chk

    output_path.write_bytes(rom)
    print(f"Wrote {output_path} ({len(rom)} bytes)")
    return output_path


if __name__ == "__main__":
    build_v301_attrinit()
