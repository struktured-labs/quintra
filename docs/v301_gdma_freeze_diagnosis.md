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

## What we still don't know

- Why per-DI cap is ~2000-3000T and not the 7000T derived from Timer ISR
  budget. Could be a different interrupt (STAT?), a vendor-specific
  mGBA timing quirk, a CGB hardware specifics our diagnosis missed, or
  the game's main loop having a tighter expectation than the ISR ceiling.
  Knowing this would let us tune the per-row DI tighter (less overhead).
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

Keep the isolation/minimal scripts as regression sentinels; remove the
freezing variants if the diagnosis doc here is enough record.
