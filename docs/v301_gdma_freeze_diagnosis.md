# v3.01 GDMA Freeze — RESOLVED (2026-05-20)

## Status: FIXED. DI window length was the real limit.

## Root cause

The diagnosis assumed the per-DI safe budget was 7000T (Timer ISR ceiling).
That was wrong. Empirically, on this ROM the safe DI budget per window is
~2000-3000T. Doing a single DI window longer than that — even well under
7000T — freezes the game at the FFC1=0→1 transition (or earlier if outside
the FFC1 gate). The freeze isn't from FF70 itself, bank-2 writes, or
attr_computation's logic — it's from one DI window holding interrupts off
for too long.

## How we found it

Binary search of progressively larger DI windows (all inside FFC1 gate):

| Variant                              | DI bytes | DI ≈ T  | Result |
|--------------------------------------|----------|---------|--------|
| FF70 toggle only                     | 9        | ~30T    | PASS   |
| + single byte write to 0xD000        | 13       | ~50T    | PASS   |
| 1 tile lookup+write inside DI        | 31       | ~80T    | PASS   |
| 1 row (24 tiles) inside one DI       | 39       | ~2000T  | PASS   |
| 2 rows (48 tiles) inside one DI      | 55       | ~4000T  | **FREEZE** |
| 3 rows (72 tiles) inside one DI      | 55       | ~6100T  | **FREEZE** |
| 2 rows in 2 separate DI windows      | 70       | 2×~2000T| PASS   |

The boundary is between ~2000T and ~4000T DI. We don't know the exact cap;
~2000T per window is safely under it.

## Fix

`create_attr_computation` now uses **24 single-row DI windows** instead of
8 three-row chunks. Each DI window writes 24 tiles to bank 2 (~2000T), then
EI for ~50T (lets Timer ISR service if pending), repeat 24 times.

Total per call ≈ 50K T-cycles (similar to the original 8-chunk design's
49K), but per-DI stays under the empirical safe budget. The row counter
lives in HRAM (FFE0) to avoid PUSH/POP nesting inside DI.

```python
def create_attr_computation(bg_table_addr):
    """24 rows × 24 tiles, each row gets its own DI window. See header."""
```

## What we verified

All probes pass on `rom/working/penta_dragon_dx_v301.gb`:

- title color: 3 distinct colors, 8.7% non-white
- gameplay palette: 21 distinct palette words, 4 attr-pal indices in use
- scroll tearing: 0.00/s pal changes, 0/s attr changes (vs vanilla 1.50/s)
- phantom D887: 0 transitions (vs vanilla 18; matches v2.99/v3.00)

## Follow-up dig (2026-05-20): the cap is NOT pure DI duration

Subsequent probes ruled out "DI length" as the actual freeze trigger:

| Variant inside one DI                                | DI ≈ T | Result |
|------------------------------------------------------|--------|--------|
| Pure NOPs                                            | 10240T | PASS   |
| NOPs with FF70=2 held throughout                     | 8000T  | PASS   |
| 96 writes via `LD [HL+], A` to bank 2                | ~1500T | PASS   |
| Flat tile_loop with bg_table lookup, 128 iterations  | 10240T | PASS   |
| Two tile_loops back-to-back, NO DE manipulation      | ~3870T | PASS   |
| Two tile_loops with `INC DE × 3` gap between         | 3920T  | PASS   |
| Two tile_loops with `INC DE × 4` gap between         | **3928T** | **FREEZE** |
| Two tile_loops with `INC DE × 8` gap between         | 3960T  | FREEZE |
| Two tile_loops with `ADD 8` gap between              | ~3914T | FREEZE |
| Two tile_loops with row_loop (PUSH AF outer)         | ~4070T | FREEZE |

The cliff is **cycle-precise**: it lands at one M-cycle (8T). Going from
N=3 INC-DE-gap (passes) to N=4 (freezes) is a difference of 8T in DI.

So it's not the DI length per se — long NOP/flat-loop DIs over 10000T pass.
The freeze requires **a memory-write pattern that crosses some specific
scheduled event during one DI window**. The most plausible suspect is
LCD STAT interrupt missing a specific mode transition: 3928T ≈ 8.6
scanlines (~456T each); blocking >8 scanlines may break a STAT-mode-0
counter the game depends on.

The per-row production fix sidesteps the issue entirely by moving the
inter-row DE advance OUTSIDE the DI window. Each per-row DI stays under
the cliff cleanly.

## What we still don't know

- Exact mechanism behind the 3920T→3928T cliff. STAT mode-counter is the
  best guess but unconfirmed. Instrumenting mGBA or checking the game's
  STAT handler at 0x0853 would clarify.
- Why the cliff materializes only with non-contiguous bank-2 writes (the
  contiguous-write 2-loops-no-gap PASSES at ~3870T which is BELOW gap-3's
  3920T — so the cliff isn't pure-time either; some interaction).
- Hardware verification on MiSTer — emulator-only proof so far.

## Side experiments left behind

- `scripts/build_v301_ff70_isolation.py` — FF70 toggle alone PASSES.
- `scripts/build_v301_bank2_write_test.py` — single bank-2 write PASSES.
- `scripts/build_v301_attr_minimal.py` — 1-tile attr_comp PASSES.
- `scripts/build_v301_attr_1row.py` — 24 tiles in one DI PASSES.
- `scripts/build_v301_attr_2rows.py` — 48 tiles in one DI FREEZES.
- `scripts/build_v301_attr_1chunk.py` — 72 tiles in one DI FREEZES.
- `scripts/build_v301_attr_2di.py` — 48 tiles split across 2 DI PASSES.
- `scripts/build_v301_attr_enabled.py` — full original 8-chunk FREEZES.
- `scripts/build_v301_per_row.py` — same fix as the main build now uses.
- `scripts/build_v301_di_nops.py` — sweep DI length with NOPs (all pass up to 6000T).
- `scripts/build_v301_di_ff70hold.py` — NOPs with FF70=2 held (all pass up to 8000T).
- `scripts/build_v301_addr_probe.py` — bank-2 writes at varied addresses (all pass).
- `scripts/build_v301_flat_loop.py` — flat tile_loops 24-128 iters (all pass).
- `scripts/build_v301_2loops_nogap.py` — two tile_loops contiguous (PASS).
- `scripts/build_v301_2rows_hram.py` — outer counter via HRAM, gap=8 (FREEZE).
- `scripts/build_v301_2rows_unroll.py` — unrolled, no outer counter, ADD 8 gap (FREEZE).
- `scripts/build_v301_inc_de_gap.py` — INC DE × N gap, N is the variable that controls the cliff.

Keep all of these as regression sentinels; the binary-search trail is more
informative than the diagnosis doc alone if someone tries to reintroduce a
"chunked" attr_comp.
