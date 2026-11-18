# Morningstar Will reach and longer Boomerang throws

Date: 2026-11-17 · Status: **implementation**
Scoped follow-up to `2026-11-15-will-scaled-b-weapons.md`. This pass covers
the Morningstar and the Boomerang only. Hookshot, Bomb Bag, and class
signatures stay as they are.

Carmelo (2026-11-17): the Morningstar should feel a little more awesome — a
wider radius at full Will, and less likely to get nerfed by obstacles. The
Boomerang should have significant travel distance, especially at full Will,
long enough to reach most of a room, with return behaviour kept sane.

## Verified on `4614675c` (headless, current main)

| Weapon | Today | Obstacle behaviour |
|---|---|---|
| Morningstar | 16-point orbit, peak **24 px**, lifetime 40 frames, damage `atk + 3`, cooldown 56, pierce 8, 16×16 head | Any non-walkable tile **cancels the swing**. A pillar or pot on the first orbit cell wastes the whole attack. In a walled corner the swing dies in ~10 frames. |
| Boomerang | Outbound **28 frames at speed 3** (85 px measured; spawn at player+4). Returns at speed 4. No damage. Will does not change range. | Pillars, pots, crystals, trees, cracked walls, and true room walls all force an early return. A mid-path pillar cut travel from 85 px to **34 px**. |

Will is not spent by either tool. There is no `will_b_tier()` helper yet.

## Design

Will is **read, not spent**. `will_b_tier()` in `will_support.c` returns 0..3
from the same values the HUD already shows:

| Tier | Condition | Player sees |
|---|---|---|
| 0 | `will_level == 0` and the bar is below one third (`will_charge < 30`) | Digit 0, empty or nearly empty bar |
| 1 | `will_level == 0` and the bar is at least one third | Digit 0, 1–2 segments lit |
| 2 | `will_level >= 1` but not cap-full | Digit 1+; a MAX is ready |
| 3 | `will_level >= WILL_LEVEL_CAP` (bar forced full, violet HUD) | Full-Will chime state |

Early game (cap 1): banking the only level jumps from tier 1 to tier 3, so
"the meter is full" is the spectacle beat. The tier is sampled on press and
kept for that swing or throw. Cooldowns and MP costs do not shrink. Damage
does not multiply; the Morningstar keeps a single damaging head (no
per-target i-frames).

### Morningstar

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 (full Will) |
|---|---|---|---|---|
| Peak radius | 24 px | 27 px | 33 px | **39 px** (~2.5 tiles) |
| Hitbox | `0xAA` 10×10 | `0xAA` | `0xCC` 12×12 | `0xDD` 13×13 |
| Damage | `atk + 3` | `atk + 3` | `atk + 4` | `atk + 5` |
| Lifetime | 40 | 40 | 44 | 48 |
| Pierce / cooldown | 8 / 56 | 8 / 56 | 8 / 56 | 8 / 56 |
| Visual | Current 16×16 head | Current | One chain link toward the hero | Two chain links, impact sparks, gold/violet flicker, `room_shake(1, 8)` on press |

Orbit points are `sx[i] * scale >> 3` with scale 8/9/11/13 (24/27/33/39 px). Trails and chain links are visual only
and do not apply damage.

**Obstacles.** The swing is never cancelled by a tile. Pillars still turn
Sun Lattice vanes, and standing stones / blast caves still register a
strike (existing debounce / idempotent open). The head is clamped to the
room bounds so it does not leave the court — that is the only "stop," and
the angle keeps ticking, so a corner no longer wastes the attack.

### Boomerang

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 (full Will) |
|---|---|---|---|---|
| Outbound frames | 28 | 36 | 44 | **56** |
| Cardinal distance | 84 px (live) | 108 px | 132 px | **168 px** |
| Return speed | 4 | 4 | 4 | 4 |
| Damage | none | none | none | none |

168 px crosses a standard 160 px room from the near side and is clearly the
longest throw. Return is unchanged: after the outbound timer, or on a
**true room wall** (`BGT_WALL`) or the room bound, the disk homes to the
hero at speed 4. Interior obstacles (pillars, pots, crystals, trees,
cracked walls, crates) no longer force an early return, so a cluttered
room does not shrink the new range. Passing a pillar or prism crystal
still calls `prism_shot_tile` (vane / prism strikes stay debounced). Fetch
set and the one-in-the-air rule do not change. Elites and bosses stay
stun-immune. Stun duration is unchanged in this pass.

## Tests

`scripts/test_will_b_weapons.py` (CI):

- `will_b_tier` via observable radius / outbound length at all four tiers,
  including cap-1 full Will and cap-4 banked-but-not-capped.
- Morningstar peak radius, lifetime, and "Will is not spent."
- Morningstar completes a full swing through pillars, pots, crystals, and
  internal wall tiles, and in a walled corner.
- Boomerang travel per tier (wide court so tier 3 is not clipped).
- Boomerang passes a mid-path pillar and still returns from a true wall.
- `test_new_game_start` and `test_sun_lattice_tools` stay green.

## Out of scope

Hookshot range, Bomb Bag splash, class signatures, boomerang stun scaling,
and cutting hostile shots. Those remain in the 2026-11-15 proposal.

## Implementation notes

- Morningstar and Boomerang code moved to bank 26 / 19 so the 256-byte
  emergency floor stays intact in the packed low banks. `will_b_tier` lives
  with the existing Will bank (11).
- A swing that no longer dies on a vane would toggle it twice in one orbit
  and leave it unchanged. The star now records a one-shot latch
  (`ai_data[5]`) so a Sun Lattice vane turns at most once per swing.
- Headless measurements on the built ROM (player-relative peak / outbound
  travel). Will is not spent.

| | Before (all Will) | After t0 | After t1 | After t2 | After t3 |
|---|---|---|---|---|---|
| Morningstar peak | 24 px | 24 px | 28.3 px | 33.9 px | **39.6 px** |
| Morningstar life, open | 40 | 40 | 40 | 44 | 48 |
| Morningstar life, pillar | **0** (cancelled) | 40 | — | — | 48 |
| Morningstar life, corner | **10** | 40 | — | — | 48 |
| Boomerang travel | 85 px | 85 px | 109 px | 133 px | **169 px** |
| Boomerang vs mid pillar | **34 px** (early return) | 85 px | — | — | 169 px |
| Boomerang vs true wall | 34 px (returns) | 34 px (unchanged) | — | — | — |
