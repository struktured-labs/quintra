# Quintra v0.3 Deep Audit — 2026-07-01

Triggered by user playtest feedback: *"where is the dungeon? I just saw a single
blank background."* Full pass over gameplay code, rendering, content, and test
harness. Findings ranked by player impact.

## TL;DR

The engine loop is sound (boot → class select → procgen rooms → boss → end
screens, all verified) but the game **reads as a blank screen** because rooms
are generated as featureless boxes over a near-black floor, several core RPG
stats are silently unwired (SPD does nothing, AI scripts ignored), and there
is no audio. The fixes are mostly content/rendering work, not architecture.

## P0 — "It doesn't look like a game"

| # | Finding | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | Rooms read as blank background | Floor palette `BGR(5,6,12)` ≈ 20% brightness; floor is a single flat tile; every room is an empty 18×16 rectangle | Brighter 4-palette scheme, 3 floor texture variants, procgen interior obstacles (pillars/crystals), per-tile CGB palette attributes |
| 2 | Walls don't read as walls | 1-tile hatch pattern, same palette as floor | Brick-face wall tile on its own (darker) palette |
| 3 | Doors nearly invisible | Small notch, same palette | Gold door-frame tile on dedicated palette |
| 4 | No sense of progression | Nothing tells you depth / that the boss is at 5 | HUD depth counter (digits already exist); minimap later |

## P1 — Silently broken mechanics

| # | Finding | Root cause | Fix |
|---|---------|-----------|-----|
| 5 | Class SPD stat does nothing | Movement hardcoded 1 px/frame during the fix8 overflow debug (SPEED_SCALE path removed); Sauran SP4 == Vespine SP7 | Sub-pixel accumulator: `acc += spd; while (acc >= 5) move 1px` → spd5 = 1.0 px/f, spd7 = 1.4 |
| 6 | Enemy `ai_script` content field ignored | `enemy_update()` hardcodes Walker for everyone; Hornet/Skeleton (Chaser) and Orc (Charger) wander randomly | Dispatch on generated `def->ai_kind`; implement Chaser + Charger |
| 7 | Boss renders as 8×8 quadrant | Entity system draws 1 OAM sprite per entity; boss uses top-left tile of its 4-tile metasprite | Reserve OAM 36–39 for the boss; special-case in `entity_draw_all` |
| 8 | Enemy may spawn on player | Spawn check applies `FIX8_TO_INT` to i16 player pos (always tile 0) AND runs before `place_player_after_entry()` | Reorder placement before spawns; compare in pixel space |
| 9 | All 5 classes share one palette | Per-class palette field exists in content but room.c loads only Wolfkin orange to OBJ pal 1 | Per-class palette table loaded at room enter (later phase) |

## P2 — Missing systems (designed, not yet built)

10. **Audio: nothing at all.** NR52 init only. Needs SFX (fire/hit/death/pickup/door)
    via pulse+noise register writes, then hUGEDriver music. Outreach to
    cowir-sfx / cowir-music sent 2026-07-02 (register-spec + note-list asks).
11. **Items never drop in-world.** 15 items defined; only heart/coin pickups
    exist. Effects/StatBoost pipeline unconsumed at runtime.
12. **Actives unusable.** A button unbound in ROOM; `signature_active` +
    `active_charge` fields dormant.
13. **Perks unimplemented.** PERK_* ids emitted but no engine hooks.
14. **No damage numbers** (spec §6), no room-clear detection
    (`rooms_cleared` never increments), no run timer.
15. **Room transitions are hard cuts.** DISPLAY_OFF/ON blink; spec calls for
    a PROCGEN cover screen.
16. **Save system absent** (Phase 8 skipped): no SRAM suspend save, no
    Continue on title, no meta-progress compendium.

## P3 — Code health

17. `fix8_t` widened to i32 for entities: works but SDCC 32-bit math on SM83
    is slow; player already moved to i16 `ppos_t`. Consider i16 fix4 (12.4)
    for entities if frame budget tightens.
18. `entity_t` is 28 B (spec said 24) — WRAM table = 896 B. Fine, spec drifted.
19. Legacy: SCRATCH debug screen, old 8×8 player/enemy/boss tiles still
    compiled in (~100 B ROM). Harmless.
20. HRAM debug markers ($FFF4–$FFFE) still written every frame. Keep for now
    (they power the Lua test harness), gate behind a DEBUG flag at 1.0.
21. Smoke test never verifies boss kill → VICTORY or death → GAMEOVER
    (input scripting can't reliably land sustained hits). Needs a
    savestate-anchored test or a cheat hook (e.g. HRAM poke = kill boss).

## What's confirmed working

- Full screen flow incl. sealed boss room at depth 5, VICTORY/GAMEOVER paths
- Procgen determinism per (run_seed, room_counter); weighted enemy pool
- Combat: 8-way fire (10/s), pierce, iframes, knock-free contact damage,
  pickup drops (30/50/20), HUD hearts+coins via WINDOW layer
- 16×16 class metasprites, per-enemy 8×8 silhouettes, muzzle/impact FX
- Rust→C content pipeline: 5 classes / 15 items / 5 enemies validate + emit
- Clean rebuild from `make cleanall`; 16/16 screenshot smoke test

## Action plan (this session)

- **Phase 14** (P0 #1–4): dungeon tileset + palettes + procgen interiors + HUD depth
- **Phase 14b** (P1 #5–8): SPD accumulator, Chaser/Charger AI, 16×16 boss, spawn fix
- P1 #9 + P2 items: subsequent phases, ordered by user steer
