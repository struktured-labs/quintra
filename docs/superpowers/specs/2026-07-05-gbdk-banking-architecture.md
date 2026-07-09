# GBDK-2020 ROM Banking — Architecture & Playbook

Status: **CONVERTED (2026-07-08).** The refactor described here landed after the
flat 32KB image silently overflowed (init code linked past 0x8000 → white
screen at boot from commit bb622c0 onward). Home is now ~11.2 KB, trampoline
at 0x28CB, screens dispatch bank-aware per §7, art+tiles co-located in bank 2
per §8, and `scripts/check_rom_layout.py` fails any build whose layout
regresses. §§1–11 below remain the reference for how and why.

---

## 1. The hardware model (Game Boy + MBC5)

- **Bank 0** — CPU `0x0000–0x3FFF` (16 KB). **Fixed, always mapped.** Holds the
  reset/interrupt vectors, the cart header, and whatever code the linker packs
  first.
- **Switchable window** — CPU `0x4000–0x7FFF` (16 KB). Shows **one** ROM bank at
  a time (bank 1 by default). Writing the MBC5 bank register (`0x2000`) swaps
  which physical bank appears here. MBC5 addresses up to **8 MB (512 banks)** +
  128 KB SRAM.

Key consequence: **code that runs while you flip the bank register must live in
bank 0**, because the `0x4000–0x7FFF` window it might be sitting in gets swapped
out from under the CPU.

## 2. Why Quintra works today *without* banking

All our code+const (~26.8 KB `_CODE`) is placed contiguously from `0x0200`,
filling **bank 0 (0x0200–0x3FFF) and spilling into bank 1 (0x4000–0x6CC2)**. We
never touch the bank register, so bank 1 stays mapped forever and the spilled
code runs fine. This is the "32 KB no-MBC" model. It stops at 32 KB total.

## 3. Why naïve banking crashes (the trap we hit)

The instant you make one banked call, SDCC emits:
```
ld   e, #b_func      ; target bank
ld   hl, #_func      ; target address (0x4000-window)
call ___sdcc_bcall_ehl   ; trampoline: save bank, switch to E, call HL, restore
```
`___sdcc_bcall_ehl` is a **library** object, linked *after* our 26 KB of code,
so it lands at **`0x7C08` — inside switchable bank 1**. When it writes the bank
register, it unmaps its own code → the next instruction fetch is garbage → hang
(blue screen). We confirmed this exact address from the linker `.noi`.

The same fate hits a manual `SWITCH_ROM` helper, `set_sprite_data` (also in
bank 1 at `0x6C55`), and the per-bank `GSINIT` loop. **Everything banking-related
needs bank 0, and bank 0 is 100% full of our code.**

## 4. The hard requirement

> **Non-banked ("home") code must fit in bank 0 — ≤ 16 KB.**

Only then does bankpack/the linker place the trampolines, `GSINIT`, and other
always-mapped machinery in bank 0, leaving banks 1+ free for banked content.
This is *all-or-nothing*: until home crosses under 16 KB, **nothing** banked
works, so you can't validate incrementally — you cross the threshold in one push.
Symptom of not being under: linker warns `Possible overflow from Bank 0 into
Bank 1` and `Multiple write of N bytes at 0x4000` (physical collisions between
home overflow and banked code).

## 5. The GBDK-2020 autobank mechanism (how it actually works)

Per-file, mark the source:
```c
#pragma bank 255            // "autobank me" sentinel (top of the .c, before includes)
```
Per public function, mark **both** the definition and the header prototype:
```c
void my_func(void) BANKED { ... }      // in the .c
void my_func(void) BANKED;             // in the .h  (so CALLERS trampoline)
```
- `#pragma bank 255` places the file's code in area `_CODE_255`.
- `BANKED` (a) forces the definition into the banked area and (b) — critically —
  makes every **caller** emit the `___sdcc_bcall_ehl` trampoline call instead of
  a plain `call`. **Both are required.** `#pragma` alone places the code in a
  bank but leaves callers doing plain jumps into an unmapped bank → crash.
- At link, `lcc -autobank` runs `bankpack`, which reassigns every `255` to a real
  free bank and reorders the objects. You'll see `Area _CODE_ NNNN 255 -> 3`.

### Makefile (the exact flags — one wrong flag silently breaks it)
```make
LCCFLAGS += -autobank      # run bankpack; auto-adds -Wm-yoA (auto bank count)
LCCFLAGS += -Wm-yt0x1B     # MBC5+RAM+BAT header byte
LCCFLAGS += -Wm-ya4        # SRAM banks
LCCFLAGS += -Wm-yC         # CGB only
# DO NOT set -Wm-yo<n>.  A fixed ROM-bank count SUPPRESSES the -Wm-yoA that
# -autobank needs and collapses all banked code back into banks 0-1. Let
# autobank size the ROM (it grows as you add banked content). Cross-checked
# against gbdk/examples/cross-platform/banks_autobank, which builds correctly.
```

### Verify banking physically worked
```python
rom = open('rom/working/quintra.gbc','rb').read()
print([b for b in range(len(rom)//16384)
       if sum(1 for x in rom[b*16384:(b+1)*16384] if x not in (0,0xFF)) > 16])
# WORKING looks like [0, 1, 2, 3, ...]; BROKEN is [0, 1] only.
```
Also check `rom/working/quintra.noi`: `___sdcc_bcall_ehl` must resolve **< 0x4000**
(bank 0). And boot-test with `mgba_run_sequence` (its inline "Freeze detected"
result is reliable; `emu:screenshot` from `run_lua` was flaky in our setup).

## 6. Target architecture for Quintra

**Home / bank 0 (keep ≤ 16 KB):**
- crt0, `___sdcc_bcall_ehl` + banking runtime, `GSINIT` (library — automatic once
  home is small).
- `main`, `loop.c` (the screen dispatcher — see §7).
- `input`, hot tiny utilities, `player`/`run_state` globals.
- The generated content tables (`enemies`, `biomes`, `items`, `classes`,
  `rooms`) **if** banked code reads them by pointer — data in bank 0 is always
  readable from any bank. (They're small, ~3 KB. Alternatively bank them behind
  accessors.)

**Banked (high banks):**
- All screen files (`title`, `room`, `class_select`, `inventory`, `gameover`,
  `victory`, `scratch`, `run_init`) — the bulk of cold code. Needs §7.
- Gameplay: `enemy_ai`, `combat`, `projectile`, `entity`, `pickup`, `procgen`.
  (Hot, per-frame — banked-call overhead ~30 cycles each; at ~a few hundred
  calls/frame that's low-single-digit % of the 70k-cycle frame. Acceptable.)
- `music`, `sfx`, `audio`.
- **All art/data:** `sprites_gen` (sprite/tile art), and future music/level data.
  Load via the RAM-staging pattern in §8.

## 7. Banked screens (the function-pointer problem + fix)

`loop.c` dispatches screens through a `const screen_t screens[]` table of
function pointers (`enter/exit/tick/draw`). A plain indirect call to a *banked*
function does **not** switch the bank → crash. Fix: make the dispatcher
bank-aware.

```c
typedef struct {
    u8 bank;                    // BANK(<any function in the screen's file>)
    void (*enter)(void);
    void (*exit)(void);
    screen_id_t (*tick)(u8, u8);
    void (*draw)(void);
} screen_t;

// table entry, e.g.:
[SCREEN_ROOM] = { .bank = BANK(room_enter), room_enter, room_exit, room_tick, room_draw },

// dispatch (loop.c stays in bank 0):
SWITCH_ROM(screens[cur].bank);
screens[cur].tick(input_keys, input_pressed);   // now the pointer target is mapped
```
`BANK(sym)` is a link-time constant, valid in a `const` initializer. Because
`loop.c` is in bank 0, and the screen fn it calls is now mapped, and any HOME
functions/data that screen fn touches are in bank 0 (always mapped), this is
safe. Screen→gameplay calls (e.g. `room_tick` → `combat_resolve` in another
bank) go through the normal `BANKED` trampolines.

## 8. Banked data (art, tables, music) — the RAM-staging pattern

`set_sprite_data`/`set_bkg_data` live in bank 0 once home is small, so you can
call them after switching to the data's bank. But cleanest and switch-proof: a
BANKED helper co-located **in the data's bank** copies to a RAM buffer, which
home code then uploads:
```c
// sprite_bank.c (same #pragma bank as the art, so it can read it directly)
void sprites_stage(u8 count16, const u8 *src, u8 *dst) BANKED {
    for (u16 i = 0, n = count16*16; i < n; ++i) dst[i] = src[i];
}
// tiles.c (home):
static u8 buf[256];
sprites_stage(4, sprite_class_wolfkin, buf);   // GBDK maps the art bank for the call
set_sprite_data(first, 4, buf);                // then upload from RAM
```
For **tables** accessed pervasively by pointer (enemies[], etc.), prefer keeping
them in home, or wrap every access in a `SWITCH_ROM(BANK(tbl)); … ` accessor.
Don't scatter raw banked-pointer dereferences.

## 9. Step-by-step conversion procedure

1. Set the Makefile flags in §5. Rebuild — game still works (no files banked yet).
2. Make `loop.c` dispatch bank-aware (§7), but keep screens **non-banked** for now
   (`.bank = 0` works while they're in home). Verify still boots.
3. In ONE push, add `#pragma bank 255` + `BANKED` (def+proto) to enough files that
   home drops < 16 KB — start with all screens + gameplay + audio, and set each
   screen's `.bank = BANK(...)`. Bank the art/data via §8.
4. Build. Confirm: no overflow/multiple-write warnings; `___sdcc_bcall_ehl < 0x4000`;
   banks list is `[0,1,2,…]`. Boot + play-through test with `mgba_run_sequence`.
5. Iterate file-by-file only for *correctness* (missing `BANKED` proto, a table
   deref from a banked fn, an ISR that must stay non-banked). ISRs and anything
   called from an interrupt **must not** be banked.

## 10. Pitfalls we actually hit (so you don't again)

- `-Wm-yt` (makebin) instead of the intended flow / leaving `-Wm-yo128` set →
  banks collapse to `[0,1]`, ROM full of `0xFF` at high banks. Use `-autobank`
  and **no** `-Wm-yo`.
- `#pragma bank` **without** `BANKED` on functions → placed in a bank but callers
  don't trampoline → jump into unmapped bank → hang.
- BANKED prototype written inside a `{}` block or missing `#include <gb/gb.h>` →
  SDCC parses it as a variable (`warning 84: 'auto' variable … used before
  initialization`) → calls garbage. Put prototypes at file scope with `gb/gb.h`.
- Home still > 16 KB → trampoline/GSINIT stranded in bank 1 → boot hang before the
  title even draws.
- `emu:screenshot` via `mgba_run_lua` was unreliable here; use
  `mgba_run_sequence` (inline freeze/OAM report) as the source of truth, and
  memory reads (`0x9800` BG map, `.noi` symbols) for detail.

## 11. Payoff

Once home is under 16 KB: the full **2 MB (or up to 8 MB)** opens up. Sprite art,
per-stage music, hand-authored levels, more bosses, cutscene data, bigger
content tables — all bankable, loaded on demand. This is the difference between a
32 KB demo and a full-size cart.
