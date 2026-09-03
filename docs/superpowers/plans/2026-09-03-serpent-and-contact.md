# Serpent Rework + Boss Contact Rebalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the stage-2 Storm Serpent genuinely hard (faster, longer/more dangerous tail, higher stats) and make touching any stage-boss body cost real HP, as the extractable first slice of the boss bullet-hell overhaul.

**Architecture:** Pure tuning of existing systems — no new files, no new mechanics. Serpent state machine timings and tail arrays change in `src/game/enemy_serpent*.c` + `enemy_ai.h`; the tail-tip volley gains a second emission point in `enemy_boss_volley.c`; stage-2 stats change in typed Rust content and flow through codegen; the colossus contact-damage cap in `combat.c` becomes a scaling formula. Every change is guarded by the existing PyBoy contract scripts, two of which pin the current values and must be updated first (test-first).

**Tech Stack:** GBDK-2020 C (SDCC), Rust content crates (`content/`, regenerated via `make gen`), PyBoy contract scripts under `scripts/`, `make verify` as the gate.

**Spec:** `docs/superpowers/specs/2026-09-03-boss-bullet-hell-design.md` (§3 contact rebalance, §4 serpent rework)

## Global Constraints

- Work only in worktree `/home/struktured/projects/penta-boss-hell` on branch `feature/boss-bullet-hell`; never touch main or the demo ROM.
- New/changed gameplay code keeps its existing `#pragma bank` headers; do not add `-Wm-yo<n>` anywhere; `scripts/check_rom_layout.py` must pass on every link (it runs inside `make`).
- `RUN_IS_EASY()` behavior must not get harder: Easy keeps 1-damage boss contact and its existing serpent blast cap.
- Do not perturb procgen RNG call order (no `rng_*` calls added or removed outside the boss fight); `uv run --with pyboy python scripts/test_procgen_parity.py` must stay green.
- All PyBoy commands run as `uv run --with pyboy python <script>` from the worktree root; `make` must be run before any script that loads `rom/working/quintra.gbc`.
- Commits end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_012B3AFxB17GK6zzq9Hzy35A`

---

### Task 1: Serpent speed-up (chase, feed, storm cadence)

**Files:**
- Modify: `src/game/enemy_serpent.c:35` (chase tick gate), `:69` (feed cadence), `:103` (storm pulse cadence)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: faster serpent that later tasks' test-timing budgets assume (charge phase pulses every 6 ticks, not 8).

- [ ] **Step 1: Build the baseline and capture current serpent behavior**

Run: `make 2>&1 | tail -3` then `uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -5`
Expected: build exits 0; test PASSes (this is the pre-change baseline; if it fails, STOP — the branch base is broken, report instead of proceeding).

- [ ] **Step 2: Apply the three cadence changes**

In `src/game/enemy_serpent.c`:

`serpent_chase_tick` — line 35, chase steps every 3 ticks instead of 4:
```c
    if (++e->state_timer < 3) return;
```

`serpent_feed_tick` — line 69, route steps every tick instead of every 2:
```c
    if (++e->state_timer < 1) return;
```

`serpent_motion_tick` — line 103, storm pulse every 6 charge ticks instead of 8 (`e->vx` counts down from 96; 96 % 6 == 0 so the first pulse still fires immediately):
```c
        if ((e->vx % 6) == 0) {
```

- [ ] **Step 3: Rebuild and re-run the serpent contract**

Run: `make 2>&1 | tail -3 && uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -5`
Expected: build 0; test still PASSes (identity assertions are about HP/structure, not cadence). If the script has cadence-sensitive frame waits that now flake, adjust only wait counts in the script, never the game code, and note it in the commit message.

- [ ] **Step 4: Commit**

```bash
git add src/game/enemy_serpent.c
git commit -m "feat(serpent): faster chase, feed, and storm cadence"
```

---

### Task 2: Tail 16 → 20 segments + dual tail volley

**Files:**
- Modify: `src/game/enemy_ai.h:43` (SERPENT_TAIL_POINTS), `src/game/enemy_serpent_tail.c:33-34` (growth targets), `src/game/enemy_serpent.c:55` (full-length gate), `src/game/enemy_boss_volley.c:44-48` (second emission point)
- Test-update: `scripts/capture_boss_gallery.py:191,193,255` (pins tail length 16)

**Interfaces:**
- Consumes: Task 1's file state of `enemy_serpent.c` (line numbers there may have shifted by ±0 — the gate is the `serpent_tail_visible < 16` expression, not the line number).
- Produces: `SERPENT_TAIL_POINTS == 21`, max `serpent_tail_visible == 20`; volley case 1 emits from tip AND midpoint. `capture_boss_gallery.py` asserts 20.

- [ ] **Step 1: Update the pinning test first**

In `scripts/capture_boss_gallery.py`, change every `16` that refers to serpent tail length (lines 191, 193, and the body-tiles read context at 255 if it compares to 16) to `20`. Example for the assertion:
```python
                assert pyboy.memory[serpent_tail_visible] == 20, \
```

- [ ] **Step 2: Run the gallery capture to verify it now fails**

Run: `uv run --with pyboy python scripts/capture_boss_gallery.py 2>&1 | tail -5`
Expected: FAIL on the tail-length assertion (ROM still grows to 16).

- [ ] **Step 3: Grow the tail in code**

`src/game/enemy_ai.h` line 43:
```c
#define SERPENT_TAIL_POINTS 21
```

`src/game/enemy_serpent_tail.c` lines 33–34 — four meals now expose 2→7→12→17→20 (cap 20, was 2→6→10→14→16):
```c
        u8 target = (u8)(2 + e->ai_data[4] * 5);
        if (target > 20) target = 20;
```

`src/game/enemy_serpent.c` line 55 — full-length gate before the charge:
```c
        if (serpent_tail_visible < 20) return;
```

- [ ] **Step 4: Add the second tail volley point**

`src/game/enemy_boss_volley.c` case 1 — after the existing tip pair (lines 44–48), emit one extra shot from the tail midpoint so the wake covers two arcs:
```c
            d = (u8)(e->ai_data[5] & 7);
            cx = serpent_tail_x[serpent_tail_visible];
            cy = serpent_tail_y[serpent_tail_visible];
            volley_shot(cx, cy, d, 1, damage);
            volley_shot(cx, cy, (u8)((d + 4) & 7), 2, damage);
            cx = serpent_tail_x[serpent_tail_visible >> 1];
            cy = serpent_tail_y[serpent_tail_visible >> 1];
            volley_shot(cx, cy, (u8)((d + 2) & 7), 2, damage);
            cadence = 30;
```

- [ ] **Step 5: Rebuild, verify the gallery passes, sanity-check identity**

Run: `make 2>&1 | tail -3 && uv run --with pyboy python scripts/capture_boss_gallery.py 2>&1 | tail -5 && uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -3`
Expected: build 0 (watch `check_rom_layout.py` — the tail arrays grew 8 bytes; if a bank overflows, report rather than repack); gallery PASS at 20; identity PASS.

- [ ] **Step 6: Commit**

```bash
git add src/game/enemy_ai.h src/game/enemy_serpent_tail.c src/game/enemy_serpent.c src/game/enemy_boss_volley.c scripts/capture_boss_gallery.py
git commit -m "feat(serpent): 20-segment tail with dual-point wake volley"
```

---

### Task 3: Stage-2 stat bump (content) + identity test update

**Files:**
- Modify: `content/src/stages.rs` (StageTheme id 1, "VERDANT HOLLOW": `boss_hp_bonus: 175 -> 190`, `boss_hp_cap: 225 -> 240`, `boss_dmg_bonus: 1 -> 2`)
- Test-update: `scripts/test_boss_identity.py:212` (asserts serpent HP == 225)

**Interfaces:**
- Consumes: nothing; independent of Tasks 1–2.
- Produces: generated `stage_boss_dmg[1] == 2`, serpent spawn HP 240. `test_boss_identity.py` asserts 240.

- [ ] **Step 1: Update the identity assertion first**

`scripts/test_boss_identity.py` line 212:
```python
    assert pb.memory[serpent + 14] == 240, (
```
(Keep the message string on the following lines aligned with the new value if it names 225.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -5`
Expected: FAIL — serpent HP still 225.

- [ ] **Step 3: Bump the content**

In `content/src/stages.rs`, StageTheme `id: 1` ("VERDANT HOLLOW"):
```rust
        boss_hp_bonus: 190, boss_hp_cap: 240, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 2, mb_variant: 1, room_archetype: 1,
```
Also update the comment above it: "The Serpent reaches 225 HP" → "The Serpent reaches 240 HP".

- [ ] **Step 4: Regenerate, rebuild, verify**

Run: `cd tools && cargo test -q 2>&1 | tail -3 && cd .. && make 2>&1 | tail -3 && uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -3`
Expected: cargo tests PASS (content validation), build 0, identity PASS at 240.

- [ ] **Step 5: Commit**

```bash
git add content/src/stages.rs scripts/test_boss_identity.py
git commit -m "feat(serpent): stage-2 boss 240 HP, damage bonus 2"
```

---

### Task 4: Boss contact-damage rebalance

**Files:**
- Modify: `src/game/combat.c` §3 hostile-contact block (~line 585): the `ENEMY_STONE_SENTINEL && ai_data[3]` colossus cap
- Create: `scripts/test_boss_contact.py`

**Interfaces:**
- Consumes: Task 3's `boss_dmg_bonus` bump (stage-2 contact expectation below assumes it; run after Task 3).
- Produces: boss contact damage = half the boss's computed hostile damage (round up, min 1); Easy unchanged at 1. New contract script `scripts/test_boss_contact.py`.

- [ ] **Step 1: Write the failing contract test**

Create `scripts/test_boss_contact.py` following the harness pattern of `scripts/test_boss_identity.py` (same imports/boot helpers — copy its preamble for ROM path, `symbol_address`, and the boss-room entry helper it uses at line ~211 to reach the stage-2 serpent):

```python
#!/usr/bin/env python3
"""Boss body contact must cost more than the old half-heart positioning tax.

Walks the hero into the serpent's body on Normal and asserts the HP loss
from a single contact tick is at least 2 (computed damage halved, min 1),
and that i-frames were granted so it is one legible hit, not a drain.
"""
# Preamble: copy ROM/bootstrap helpers from test_boss_identity.py verbatim.

def main():
    pb, serpent = enter_boss(1, keep_open=True)   # stage-2 serpent, as in test_boss_identity.py:211
    player_hp = symbol_address(ROM, "_player") + 2
    iframes = symbol_address(ROM, "_player") + PLAYER_IFRAMES_OFFSET  # find offset in src/game/player.h
    hp_before = pb.memory[player_hp]
    # Drive the hero straight at the boss head until contact registers.
    for _ in range(600):
        pb.button_press("up"); pb.tick(2); pb.button_release("up"); pb.tick(1)
        if pb.memory[player_hp] < hp_before:
            break
    loss = hp_before - pb.memory[player_hp]
    assert loss >= 2, f"boss contact cost {loss}, expected >= 2 on Normal"
    assert pb.memory[iframes] > 0, "contact granted no i-frames"
    print(f"PASS boss contact loss={loss}")

if __name__ == "__main__":
    main()
```
Resolve `PLAYER_IFRAMES_OFFSET` from the `player_t` struct layout in `src/game/player.h` before running (count bytes to the `iframes` field); if `enter_boss` in `test_boss_identity.py` is module-level, import it instead of copying.

- [ ] **Step 2: Build and run to verify it fails**

Run: `make 2>&1 | tail -3 && uv run --with pyboy python scripts/test_boss_contact.py 2>&1 | tail -3`
Expected: FAIL with `boss contact cost 1, expected >= 2` (current cap).

- [ ] **Step 3: Replace the flat cap with the scaling formula**

In `src/game/combat.c`, the hostile-contact block (search for the string `positioning tax`):
```c
                u8 taken = status_hostile_damage_taken(i);
                if (entities[i].type == ENT_ENEMY
                    && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
                    && entities[i].ai_data[3]) {
                    // Boss body contact is half its computed hit (round up,
                    // min 1): a real cost that scales with the stage without
                    // turning the body into a second full-strength bullet.
                    taken = (u8)((taken + 1) >> 1);
                    if (!taken) taken = 1;
                }
```
Update the surrounding "positioning tax" comment to describe the new rule (delete the sentences that say contact is kept at one half-heart). The `if (RUN_IS_EASY()) taken = 1;` line a few lines below already restores Easy — leave it exactly where it is (after the boss branch).

- [ ] **Step 4: Rebuild and verify pass + no Easy regression**

Run: `make 2>&1 | tail -3 && uv run --with pyboy python scripts/test_boss_contact.py 2>&1 | tail -3 && uv run --with pyboy python scripts/test_boss_identity.py 2>&1 | tail -3`
Expected: contact test PASS with loss >= 2; identity PASS. Then grep the smoke assertions: `command grep -rn 'hp=' scripts/test_smoke.sh | head` — if any pinned HP range assumes half-heart boss contact along the smoke route, adjust that range in the script and say so in the commit message.

- [ ] **Step 5: Commit**

```bash
git add src/game/combat.c scripts/test_boss_contact.py
git commit -m "feat(combat): boss body contact scales with boss damage"
```

---

### Task 5: Full gate + fold-readiness report

**Files:**
- No source changes. Test: full suite.

**Interfaces:**
- Consumes: Tasks 1–4 complete.
- Produces: a fold-ready branch and a summary (posted back to the session lead) with the new ROM's sha256.

- [ ] **Step 1: Run the full verification suite**

Run: `make verify 2>&1 | tail -20`
Expected: every stage green, including cargo tests, smoke 28/28, procgen parity 12/12, budget report. This takes a while (~83 PyBoy launches); run it in the background and check the tail. If `report_budget.py` fails on bank headroom, report the exact numbers — do NOT trim unrelated code to make room.

- [ ] **Step 2: Difficulty sanity capture**

Run: `uv run --with pyboy python scripts/capture_boss_gallery.py 2>&1 | tail -8`
Expected: PASS; note in the report whether the scripted route now takes hits at the serpent (it should — that is the point).

- [ ] **Step 3: Record the ROM hash and report**

Run: `sha256sum rom/working/quintra.gbc`
Report: branch name, 4 commit shas, ROM sha256, verify status, any script assertions adjusted. Do not merge; the fold decision belongs to the owner.
