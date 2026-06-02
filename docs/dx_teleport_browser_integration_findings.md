# DX Teleport Browser Integration — Why It Doesn't Work (yet)

(2026-06-01, partial investigation. The in-game combo cycling **does**
work — see `scripts/build_v301_teleport.py` tag `v3.01-teleport-all-bosses`.
This doc covers the failed attempt to also wire the browser-side
"DX Teleport" buttons through `DF0A`.)

## What we tried

The live palette editor (`scripts/live_palette_editor.py` +
`scripts/lua/live_palettes.lua`) already has a "DX Teleport" section
with one button per boss (Shalamar..Penta Dragon). Clicking writes
`DX:N` to `/tmp/live_palettes.txt`. The Lua bridge reads that file
every ~30 frames and writes `DF0A = N` (1..9) into the running game's
WRAM, expecting a ROM-side hook to consume it.

Plan was to add a ~30-byte DX entry path at the top of our v16 teleport
routine (the "v17" attempt):

```asm
; runs every VBlank from our 0x6E80 teleport routine
LD A, [DF0A]
OR A
JR Z, normal_path   ; DF0A=0 → unchanged behavior, fall to combo check
; --- DX fire path: only reached if DF0A != 0 ---
DEC A               ; A = boss index 0..8
LDH [FFBA], A
XOR A
LD [DF0A], A        ; clear request
LD A, 1
LD [DF0C], A        ; set debounce
LD A, 60
LD [DF1F], A        ; set colorize sit-out
LD A, 30
LD [DF1D], A        ; set re-fire gate
JR fire_tail        ; HP setup + stack redirect (shared with combo fire)
normal_path:
; ... existing combo check + fire path ...
```

## What broke

| Variant | mgba behavior | PyBoy behavior |
|---------|---------------|----------------|
| v16 (no DF0A logic at all) | stable, combo cycles bosses | stable |
| v17b (DF0A read only, no fire path) | stable | identical to v16 over 1100f |
| v17 (full DX path, 30 bytes added) | **freezes ~5 sec after start** | **runs fine, cycles bosses** |

So:
- The ROM is **logically correct** — both PyBoy and a frame-by-frame
  static trace agree the JR Z bypass is taken when `DF0A=0`, the DX
  fire path is unreachable, and `LD A, [DF0A]; OR A; JR Z` adds ~28T
  per VBlank, far under any timing budget.
- The failure is **specific to mgba-qt 0.10.5** (`v3.01-teleport-all-bosses`
  ROM == v16 works there; same ROM + 24 unreachable bytes of DX fire
  path == hangs).

## Diagnostic state

| Address | What it holds | Confirmed game-writable? |
|---------|---------------|--------------------------|
| `DF0A`  | DX teleport request slot (legacy, named in `live_palettes.lua`) | static-scan-clean |
| `DF0E`  | landing-pad-copy sentinel (`0x5A` = WRAM 0xDB00 holds the pad) | scan-clean |
| `DF0C`  | combo debounce (`1` while held) | scan-clean |
| `DF1D`  | re-fire sit-out (30 frames after a fire) | scan-clean |
| `DF1F`  | colorize-skip counter (60 frames after a fire) | scan-clean |
| `DF20/21` | saved main-loop PC for landing pad's `JP HL` back | scan-clean |
| `0xDB00` | runtime landing pad (40 bytes copied from bank13:0x6F80) | **not verified safe** |

PyBoy run shows v17 reaches the title screen, cold-boot runs once
(`DF0E` becomes `0x5A`), `DF0A` stays `0`, the JR Z bypass is taken
every frame, combo check runs normally. Trajectory matches v16 to
the cycle.

## Hypotheses for the mgba-only freeze

Ordered by my current confidence:

1. **WRAM 0xDB00 collision (most likely).** The landing pad lives at
   WRAM 0xDB00 and we never verified that range game-safe. When the
   game's main loop reaches state that writes to 0xDB00-0xDB27, it
   overwrites the landing pad code with garbage. The next time DX
   fires, `RETI` lands on garbage → freeze. The 24 bytes of extra DX
   fire path shift the ROM layout by 24 bytes and may coincidentally
   nudge the game into a different code path that touches `0xDB00`
   earlier, hence "freeze ~5 sec." PyBoy may use a different WRAM
   timing model that avoids the collision.

2. **OAM DMA / mode-3 timing.** mgba's LCD-mode timing is stricter
   than PyBoy's. The 24 extra bytes add ~50T to the worst-case path,
   nudging some VRAM/CRAM write past mode 0 into mode 3 where it gets
   dropped. Symptoms: visual freeze (the last good frame stays on
   screen) while CPU is still running normally. Worth checking with
   mgba's logging / `LCDC.7` watch.

3. **Stale `.sav` SRAM or mgba state file.** The user reported the
   freeze persists across "reset" in mgba. mgba auto-loads `.sav` for
   battery-backed SRAM. Although Penta Dragon doesn't appear to use
   SRAM heavily, mgba may be loading state we don't expect. Re-test
   after `rm rom/working/penta_dragon_dx_teleport.sav` and clearing
   `~/.config/mgba/cache.*` if any.

4. **IRQ recursion via the IE register.** v17 doesn't touch IE, but
   it does set `DF0C` (debounce) `DF1D` and `DF1F`. If the colorize
   handler re-enters during arena init (which the existing v16 colorize
   sit-out is supposed to prevent), and our DX path runs before the
   sit-out, we may get unbalanced PUSH/POP on the IRQ stack. We did
   not get this far before in v16 because the combo debounce flow
   prevented re-entry; the DX flow may be one PUSH/POP short.

## Workaround that's actually live

v17b (the minimal `LD A, [DF0A]; OR A; JR 0`) is stable and **does
read DF0A**, just doesn't act on it yet. So the wiring half exists:
the Lua bridge can write DF0A, the ROM reads it. The ROM just doesn't
do anything with the value.

Possible workaround paths to wire the browser through without the
freeze-trigger:
- **Lua forces FFBA + simulates combo.** Lua writes `FFBA = N-1`,
  then writes `FF93 = 0x0C` for one frame. The existing combo path
  fires, calls `INC FFBA`, ends up on the next boss. Not exactly the
  user's pick (off by one), but close. Could be fixed by Lua writing
  `FFBA = N-2` first (with the -1 wrap to 0xFF case handled).
- **In-place DF0A consumer in landing pad.** Instead of the DX fire
  path in the teleport routine, write the consumption logic into the
  WRAM landing pad — we already control 40 bytes there. The landing
  pad runs in main-loop context where the (suspected) mode-3/timing
  issue from hypothesis 2 wouldn't bite.
- **Re-verify the 0xDB00 region.** Run a long-form WRAM probe with a
  watchpoint on 0xDB00-0xDB27. If anything writes there, relocate the
  landing pad to a confirmed-safe region.

## Reproduction

```bash
# Stable, no DX wiring
git checkout v3.01-teleport-all-bosses scripts/build_v301_teleport.py
python3 scripts/build_v301_teleport.py
mgba-qt rom/working/penta_dragon_dx_teleport.gb

# v17 (the freezing version) — investigate further
# (build script saved at /tmp/build_v17_dx_attempt.py during the 2026-06-01 session)
```

The build script for v17b (read-only DF0A probe) was left at
`scripts/build_v17b.py` for future regression testing. It produces
`rom/working/penta_dragon_dx_teleport_v17b.gb`. Identical behavior
to v16 in both mgba and PyBoy.
