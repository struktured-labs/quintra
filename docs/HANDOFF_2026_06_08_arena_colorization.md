# Handoff — boss-arena colorization (2026-06-08)

Recap before context compaction. Goal ("holy grail"): color each boss arena
with **no color alternation** and **no shared boss/background tile bleed**.

## TL;DR state
- **`main` is the safe shipping state**: data-driven tile-ID bg_tables for all
  9 bosses (animation-stable assignment; reduced the rainbow, but does NOT
  fully kill alternation — that's the tile-ID ceiling).
- **GDMA position-blit is DEAD** for arenas (proven). Quarantined on branch
  `wip-arena-gdma-position`. Do not merge.
- **Next path: position-based `bg_sweep`** (CPU writes, no HDMA) — not yet built.

## The problem & root cause
Boss is a **BG-layer** sprite, colorized **by tile ID** (inline hook at
bank1:0x42A7 + bg_sweep safety net). Two user-rejected artifacts:
1. **Alternation** — a cell's palette flips frame-to-frame. Cause: the
   1-row/frame bg_sweep can't keep up with boss animation; cells show stale
   palettes between sweeps. Measured 134 alternating tiles on Shalamar.
2. **Shared tiles** — one tile ID used by boss AND background gets one color.
Both are inherent to tile-ID keying. The "bob" is a SCX/SCY scroll-shake
(FF42/FF43 oscillate), NOT tilemap movement — so position-based coloring in
tilemap space is bob-proof (this licensed the GDMA/sweep idea).

## What was PROVEN
- **Lua prototype** (per-frame position blit, banded relative to live boss top,
  floor-gated): alternation 134 → ~8 flips, background clean. Algorithm is
  correct. See `scripts/diagnostics/proto_position_blit_relative.lua`.
- **In-ROM GDMA position-blit**: KILLS alternation (0 ATTR-FLIPs) BUT collapses
  the arena (D880 0x0C→0x01 in ~170 frames).
- **Parallel isolation matrix** (stability = % of 300 frames arena survives):
  - teleport wiring only (no GDMA): **100%** → wiring innocent
  - per-frame GDMA, sizes 16B/128B/288B/576B: **6–7% (size-independent)**
  → GDMA *operation* (not halt time) is fatal. Leading cause: **HDMA-engine
  conflict** — the arena uses HBlank-HDMA for the scroll-shake; a general-mode
  GDMA terminates it every frame. (Letta review Caveat 2 confirmed.)
  Full data: `docs/FINDINGS_2026_06_07_arena_gdma_isolation.md` (on the branch).

## The pivot (recommended next build)
**Position-based `bg_sweep`.** The existing bg_sweep writes attrs with plain
CPU stores — **no HDMA** — and already coexists with the arena (it ships on
main; arenas stay stable). Plan:
1. In arena scenes only (D880 0x0C..0x14), make the sweep write a
   **position-band** attr (by tilemap row, relative to the boss's stable top)
   instead of `bg_table[tile]`, and **floor-gate** (skip tile<=0x01) so the
   background stays default.
2. Cover **enough rows/frame** to keep up with animation (1 row/frame is too
   slow → alternation; the dungeon "fast-sweep" did N rows/frame).
3. FIRST verify the sweep's timing structure: `create_bg_sweep_viewport_gated`
   in `scripts/build_v296_phantomsafe.py` — does it STAT-wait (safe to add
   rows, spreads across frame) or run VBlank-only (multi-row overruns)? That
   determines max rows/frame.
4. Per-arena footprint maps already probed:
   `scripts/diagnostics/footprint_maps.log` (Shalamar tight rows 0-8; busy
   arenas Riff/Crystal/Cameo/Troop are full-screen banded — user OK'd that).
5. Verify with the stability probe (`/tmp/probe_stability.lua` pattern) AND
   the alternation probe before claiming fixed.

Fallback if the sweep also can't keep up: accept main's tile-ID tables.

## Key facts / addresses
- D880 scene: 0x02 dungeon, 0x0C..0x14 = the 9 arenas (Shalamar..Penta), 0x18
  boss splash, 0x01 title, 0x00 uninit. FFBA = boss index 0..8.
- Inline hook 0x42A7 (bank1): reads tiles from WRAM **0xC1A0** (NOT a clean
  row-mirror of VRAM 0x9800 — verified), writes attr=bg_table[tile] via [BC].
- bg_sweep at bank13:0x6CD0 (1 row/frame, DF04 counter). GDMA at 0x6D80 (dead
  on main, used on branch). Dead `attr_comp` at 0x7100. Free gap ~0x6B27 (233B).
- Colorize handler 0x6E00; teleport routine 0x6E80; scene_detect 0x6FB0;
  arena bg_tables 0x7200..0x7AFF (256B each, page-aligned dispatch).
- "GDMA"/`attr_comp` in build_v301_gdma.py are DEAD CODE (never CALLed) — the
  live colorizer is the v3.00 inline hook. See FINDINGS_2026_06_07_gdma_is_dead_code.md.

## Pipeline & tooling
- Build teleport ROM: `python scripts/build_v301_teleport.py` →
  `rom/working/penta_dragon_dx_teleport.gb`.
- Tables: `probe_all_tables.lua`/`probe_arena_tables.lua` → logs →
  `apply_arena_tables.py` → `scripts/arena_tables_data.py` (tile-ID keyed;
  WRONG shape for position approach — would need new CELL-indexed maps).
- Diagnostics in `scripts/diagnostics/` (alternation, boss-coord, footprint,
  timeseries, position-blit proto).
- Live editor: `./scripts/palette_session.sh start` → http://localhost:8077.
  live_palettes.lua skips palette pushes in arenas now (don't clobber arena
  CRAM). Teleport via DX:N file directive / browser buttons.

## Gotchas
- **mGBA launch is flaky** (Wayland + headless xvfb). Use `setsid nohup env
  DISPLAY=:0 QT_QPA_PLATFORM=xcb /home/struktured/bin/mgba-qt ... & disown`;
  verify via `/proc/PID/exe` (pgrep -f matches bash wrappers). Often needs a
  2nd attempt. Parallel headless: `xvfb-run -n <N>` with explicit display nums.
- **Combo teleport is unreliable** (~50% land; ted/faze/angela/penta worst).
  Hold Sara HP (DCDC/DCDD=0xFF) every frame during arena probes or she dies.
- **Verify on MiSTer hardware** before promoting any colorizer change — GDMA
  freeze history is hardware-specific; the arena is timing-sensitive.

## Recent commits (main)
- arena tables data-driven + corner-floor filter; FIXED.gb re-synced to v3.01;
  198G leaked tmp wav + 744 committed capture files purged.
- Branch `wip-arena-gdma-position`: GDMA experiment + isolation findings.
