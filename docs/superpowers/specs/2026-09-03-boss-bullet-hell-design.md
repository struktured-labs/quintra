# Boss Bullet-Hell Overhaul

Date: 2026-09-03
Status: approved (struktured, in-chat)
Branch: `feature/boss-bullet-hell`

## Goal

Bosses should feel like bullet-hell encounters: telegraphed but punishing
patterns, meaningful body contact, and escalation as HP drops. The stage-2
Serpent is the flagship rework — it is currently far too easy — and its
slice must remain cherry-pickable on its own (it may ship ahead of the
rest).

Owner directives driving this spec:

- Serpent: faster, tail "even more obnoxious", higher stats.
- Bullet hell "should really be a thing" for all bosses.
- Body damage when touching a boss hitbox.
- New attack shapes: debris shaken onto the board, minion summons, and an
  AOE where only ~25% of the arena is safe.
- Boss sprite art needs work; **serpent art only** is in scope here. Other
  bosses' art is a separate later effort.

## Current state (verified in code)

- `src/game/enemy_boss_volley.c` — per-boss volley patterns keyed on
  `ai_data[2]`, one cadence scheduler via `ai_data[1]`. Cadence already
  tightens below half HP (`boss_volley_tick` tail).
- Void Lord (case 8) already implements an announced-safe-pocket
  room-wide blast ("World Collapse") — the AOE primitive exists in
  bespoke form for one boss.
- `src/game/combat.c` §3: enemy/boss bodies already damage the player on
  overlap, but colossus contact is deliberately a half-heart
  "positioning tax". Uses existing i-frame + knockback machinery.
- Serpent: `enemy_serpent.c` (feed→charge→coil state machine, 16
  waypoints, proximity blast), `enemy_serpent_tail.c` (2..16 visible
  segments), `enemy_serpent_pulse.c` (storm motes), `enemy_serpent_draw.c`.
- Boss stats flow from typed Rust content: `content/src/stages.rs`
  (`boss_hp_bonus`, `boss_hp_cap`, `boss_dmg_bonus`, `mb_variant`, ...)
  through quintra-codegen into `src/generated/stages.*`.
- Entity table is 32 slots; minions must not starve it.

## Design

### 1. Pattern library — `src/game/boss_patterns.c` (new, banked)

Three reusable primitives sharing the existing `ai_data[1]` cadence
scheduler so they interleave with volleys rather than replacing them:

- **`pattern_debris(e, density, telegraph, damage)`** — shadow markers
  (via `fx_spawn`) appear on N random walkable tiles for `telegraph`
  frames, then each becomes a short-lived damaging hazard entity plus
  `room_shake`. Hazards reuse projectile-style slots and expire.
- **`pattern_summon(e, roster_slot, count)`** — spawn `count` (2–3)
  minions from the stage's normal enemy roster. Hard gate: only when at
  least 8 entity slots are free; otherwise the pattern is skipped this
  cycle (never queued).
- **`pattern_aoe_safezone(e, telegraph, quadrants, blast)`** — the Void
  Lord's World Collapse generalized: announce 1..`quadrants` safe
  pockets, telegraph, then a room-wide blast that spares players inside
  a pocket (Manhattan radius check as today). Void Lord case 8 becomes
  the first consumer of the shared primitive; its observable behavior
  must not regress (same telegraph length, same safe spots, same Easy
  damage cap).

Telegraph philosophy: every new hazard gets a 30–60 frame visual cue at
160x144 legibility; punishment for ignoring it is severe on Normal,
capped on Easy exactly like existing patterns (`RUN_IS_EASY()`).

### 2. Content schema — boss phases

`content/src/stages.rs` gains per-stage `boss_phases`: up to 3 entries of
`{ hp_threshold_pct, patterns: &[PatternRef], tempo, density }` where
`PatternRef` names a primitive plus its parameters. Codegen emits a C
table; `boss_volley_tick`'s scheduler consults the active phase (highest
threshold ≥ current HP%) to decide which pattern fires next.

Validation at `cargo build` (quintra-content `Registry::validate()`):

- thresholds strictly descending, first is 100;
- pattern parameter ranges (telegraph 30..=90, summon count 1..=3,
  quadrants 1..=2, density 1..=8);
- summon patterns only on stages with a non-empty roster;
- table size fits the generated C array budget (`report_budget.py` gate
  unchanged).

Negative tests accompany each new validation rule (the 2026-07-27 audit
flagged validator coverage; new validators do not repeat that gap).

### 3. Contact-damage rebalance

Boss body contact scales with the stage's `boss_dmg_bonus` instead of the
flat half-heart: `taken = 1 + boss_dmg_bonus` (so stage 1 ≈ 2, stage 9 ≈
4 half-hearts), Easy stays at 1. Ordinary enemies unchanged. Implemented
in the existing `combat.c` §3 block — no new collision path, same
i-frames/knockback, Riftwild recovery rule untouched.

### 4. Serpent rework (phase 1 — extractable slice)

Existing knobs only; no dependency on §1–§3. This slice alone must leave
`make verify` green and is the candidate for early shipping.

- Chase tick gate 4 → 3; feed step cadence 2 → 1 (faster route + charge).
- Tail: max visible segments 16 → 20 (`enemy_serpent_tail.c` arrays and
  `serpent_tail_visible` bounds); wake volley (`enemy_boss_volley.c` case
  1) fires from two tail points (mid + tip) instead of one.
- Storm pulse cadence every 8 frames → 6 during charge.
- Content: stage-2 `boss_hp_bonus`/`boss_dmg_bonus` bump (exact numbers
  tuned against the existing serpent contract test until the scripted
  baseline controller no longer wins without taking hits).

### 5. Serpent art pass

New head, body-segment, and tail-tip tiles authored in
`tools/crates/quintra-assets` ASCII grids — meaner silhouette, head
readable against all stage-2 palettes, distinct tail tip, damage-flash
variant. Golden test updated alongside (byte-identical check regenerated
once, reviewed, then frozen again).

## Out of scope

- Art for bosses other than the serpent.
- New audio (existing SFX reused: `SFX_ROAR`, `SFX_TICK`, `SFX_DEATH`).
- Mini-boss and elite behavior.
- Any change to the demo/live ROM until the owner folds this branch.

## Testing

- Per-pattern scripted PyBoy contract tests (`scripts/test_boss_debris.py`
  etc.): telegraph visible → hazard live → scripted safe conduct survives
  → scripted greedy positioning takes the expected damage.
- Void Lord regression: existing behavior byte-compared where practical
  (same telegraph cadence and safe-spot table) after migration to the
  shared primitive.
- Serpent contract tests updated for new timings; a difficulty assertion
  that the scripted baseline route now takes ≥1 hit on Normal.
- Rust: negative validation tests per new rule; codegen output test for
  the phases table.
- `make verify` (includes procgen parity — patterns must not touch RNG
  call order outside boss rooms) green before any fold.
- Bank budget: new code goes in a warm bank via `#pragma bank 255` +
  `BANKED`; `scripts/check_rom_layout.py` and `report_budget.py` gate as
  usual.

## Build order

1. Serpent tuning (§4) — extractable.
2. Contact rebalance (§3).
3. Pattern library + content schema + validation (§1, §2).
4. Void Lord migration to shared AOE.
5. Debris/summon/AOE rollout across bosses 1–8 via content phases.
6. Serpent art (§5).
