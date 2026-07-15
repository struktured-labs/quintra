# Shadow-OAM write interception plan

ROM analyzed: `rom/working/penta_dragon_dx_teleport.gb` (262,144 bytes, SHA-256 `758cbc7ddedd33da303d2504aebc7cdcdbfebd525d7775dd2097c680498fb5fd`). This is a read-only static analysis; the ROM was not modified.

## OAM Write Sites Found

### Result and scope

The SM83 has no instruction which encodes an immediate 16-bit destination except `LD [a16],A` and `LD [a16],SP`. An exhaustive byte search found **no executable direct-address store to `$C000-$C09F`**. The three apparent matches (`bank 6:$5F86`, `bank 12:$7282`, and `bank 15:$5C25/$69B6`) are embedded data, not aligned reachable code.

All real writes are indirect. The following sites are proven by disassembly and register flow. “Bank 0” is fixed ROM and is visible regardless of the switchable bank.

| CPU address | Bytes / instruction | Register state at the write | Bank | Role |
|---|---|---|---|---|
| `$09A2` | `22` — `LD [HL+],A` | `HL=$C000..$C09F`; `A` is the caller's fill value; `B` is the byte count | 0 | Generic fill helper. Proven callers clear shadow entries/ranges, including the 40-entry loop beginning at `$1ED5` and clear helpers at `$4931/$494A` (bank 1). |
| `$09B5` | `12` — `LD [DE],A` | `DE=$C000..$C09F`; `A=[HL]`; `HL` is source; `BC` is remaining byte count | 0 | Generic `memcpy` loop (`$09B3`: save A; `$09B4`: `LD A,[HL+]`; `$09B5`: store; `$09B6`: `INC DE`). Used by sprite/table loaders as well as non-OAM copies. Calls at `$1F0C`, `$28E5`, and `$36DE` copy **from** C000 **to** C100 and therefore do not themselves write the requested range. Other callers can copy into C000. |
| `$10D3` | `12` — `LD [DE],A` | `DE=entry+0`; `A=B` (Y) | 0 | Four-byte sprite emitter. Callers pass a C000-region destination. |
| `$10D6` | `12` — `LD [DE],A` | `DE=entry+1`; `A=C` (X) | 0 | Same emitter. |
| `$10D9` | `12` — `LD [DE],A` | `DE=entry+2`; `A=[HL+]` (tile ID) | 0 | Same emitter; this is the best palette interception point. |
| `$10E2` | `12` — `LD [DE],A` | `DE=entry+3`; `A` is the attribute produced by calls `$11A2` and `$1188` | 0 | Same emitter; writes the DMG attribute/flip byte. |
| `$3484` | `22` — `LD [HL+],A` | `HL=free entry+0`; `A=B` (Y) | 0 | Free-slot sprite emitter; `$346F` starts at C000 and advances by four until an empty entry is found. |
| `$3486` | `22` — `LD [HL+],A` | `HL=entry+1`; `A=C` (X) | 0 | Same emitter. |
| `$3488` | `22` — `LD [HL+],A` | `HL=entry+2`; `A=D` (tile ID) | 0 | Same emitter; second best interception point. |
| `$3498` via `$09B5` | `CALL $09B3`, count 3 | `DE=corresponding C100 entry`; source is the three bytes just written in C000 | 0 | Copies Y/X/tile to the alternate buffer; it does not write C000-C09F after entering memcpy. |
| `$5218` | `12` — `LD [DE],A` | `DE=entry+0`; `A=B` (Y) | 1 | Bank-1 four-byte emitter (`$5217`). |
| `$521B` | `12` — `LD [DE],A` | `DE=entry+1`; `A=C` (X) | 1 | Same emitter. |
| `$521F` | `12` — `LD [DE],A` | `DE=entry+2`; `A=[HL+] & $0F` (tile ID) | 1 | Same emitter; palette interception point. |
| `$5222` | `12` — `LD [DE],A` | `DE=entry+3`; `A=[HL+]` (attribute) | 1 | Same emitter. |
| `$1EEA` | `22` — `LD [HL+],A` | `HL` walks a selected C000 entry; `A=0`; `C=4` | 0 | Clears all four bytes of an entry. This is deletion, not creation, so no lookup is useful. |
| `$1EFB,$1EFE,$1F01,$1F03` | `22/77` stores | `HL=$C07C..$C07F`; `A=$78,$0C,$1D,$00` respectively | 0 | Installs one fixed sprite: Y, X, tile `$1D`, attr zero. |
| `$3630` | `36 00` — `LD [HL],$00` | `HL=$C09C` | 0 | Clears the last entry's Y byte. |

Static disassembly can prove these paths, but cannot mathematically prove that an indirect generic helper never receives another computed C000-range pointer. An execution-coverage claim of “all paths in the game” would additionally require write-watchpoint traces across every game mode. The sites above cover the central emitters, fixed-slot emitter, clear path, and generic copy/fill primitives visible in the ROM.

## Hook Design Per Site

### Important correction to the 6–8-byte premise

A complete lookup and attribute merge cannot fit in 6–8 SM83 bytes. The viable 6–8-byte **inline patch** is a call to an out-of-line, always-mapped bank-0 trampoline, padded with NOPs. The trampoline performs the lookup and then reproduces the displaced instructions. Calling bank-13 code directly is unsafe because the active switchable bank varies; the trampoline must either live in bank 0/WRAM or save `$FF99`, map bank 13, and restore both the MBC register and `$FF99`.

The hook must preserve attribute bits 3–7 and replace only bits 0–2:

```asm
new_attr = (original_attr & $F8) | (table[tile] & $07)
```

`$FF` in the table is a dynamic-Sara marker, not a legal OAM attribute. Resolve it to palette 2 when `[$FFBE]==0`, otherwise palette 1.

### `$10D9/$10E2` central emitter (recommended)

- Replace 7 bytes at `$10D8`: `2A 12 13 2A CD A2 11` (tile load/store, destination increment, attribute load, and the complete first attribute-transform call).
- Inline hook: `CD ll hh 00 00 00 00` — `CALL central_oam_hook`, four NOPs.
- The trampoline enters with `HL` pointing at the tile source and `DE=entry+2`. It reproduces `LD A,[HL+]; LD [DE],A`, retains tile in a scratch register/stack, advances DE, loads the original attribute from `[HL+]`, performs both original attribute-transform calls (`$11A2`, `$1188`), merges the LUT palette, writes `[DE]`, and advances DE. It then discards the inline CALL return address and jumps to `$10E4`, after the displaced remainder (`CALL $1188; LD [DE],A; INC DE`). This tail-continuation detail is mandatory; an ordinary `RET` would execute the second transform/store twice.
- Register contract after the trampoline: `DE` and `HL` match the original post-attribute state; `BC`, `AF`, flags, and SP match the original continuation except for flags that the following original code does not consume. Conservatively push/pop AF and BC.

### `$3488` free-slot emitter

- Replace 6 bytes at `$3487`: `7A 22 F5 C5 D5 E5` (`LD A,D; LD [HL+],A; PUSH AF/BC/DE/HL`) with `CD ll hh 00 00 00`.
- Inline hook: `CD ll hh 00 00 00`.
- Trampoline writes tile `D` to `[HL+]`, looks up `table[D]`, writes the merged attribute to the now-current `[HL]`, then reproduces the four pushes before returning to `$348C`. This site previously copied only three bytes to C100, so the hook must also arrange for the attribute to be mirrored to the corresponding C100 byte (or expand the later copy count from 3 to 4).
- Register contract: all live registers and the four pushed stack values must be exactly as at original `$348C`; only the C000/C100 attribute bytes change.

### `$521F/$5222` bank-1 emitter

- Replace 7 bytes at `$521D`: `2A E6 0F 12 13 2A 12` (tile fetch/mask/store, increment, attribute fetch/store).
- Inline hook: `CD ll hh 00 00 00 00`.
- Trampoline reproduces the tile mask, stores the tile, retains it for the LUT, fetches the original attribute, merges palette bits, stores the attribute, and returns at `$5224` (before the original `INC DE`).
- Register contract: `HL` has advanced twice, `DE=entry+3`, A contains the merged attribute rather than the original attribute. If subsequent code relies on A, restore the original A after the store; the immediately following code only increments DE and recomputes C.

### Fixed sprite `$1EF9-$1F03`

- Replace 6 bytes beginning at `$1EFF`: `3E 1D 22 AF 77 AF` with `CD ll hh 00 00 00`.
- The trampoline emits tile `$1D` and a LUT-derived attribute, then leaves `A=0` and returns at `$1F05` for the following `LD [$DCDD],A`. Since tile `$1D` is the dynamic-Sara range, resolve `$FF` through `$FFBE`.
- Preserve HL at `$C080` (the original state after four writes) and preserve the original final A=0 if live.

### Generic clear/fill/copy sites

Do **not** palette-hook `$09A2`, `$09B5`, `$1EEA`, or `$3630` per byte. They lack OAM-field phase information and are also used for non-OAM memory. A lookup there would color deleted entries, corrupt ordinary copies, and add cost per byte rather than per sprite. Leave clears unchanged. For copies into C000, hook their call sites after the copy only if runtime tracing reveals a producer that bypasses all three semantic emitters above.

## Palette Lookup Table Design

The compiled ROM already contains the desired page-aligned 256-byte table at bank 13 `$6B00` (file offset `$36B00`). Reuse it rather than creating a conflicting table:

| Tile IDs | Stored value | Meaning |
|---|---:|---|
| `$00-$01` | 3 | projectiles |
| `$02-$0F` | 0 | effects |
| `$10-$2F` | `$FF` | dynamic Sara: palette 2 if `FFBE=0`, otherwise 1 |
| `$30-$4F` | 3 | enemies |
| `$50-$5F` | 4 | hornets |
| `$60-$6F` | 5 | enemy class |
| `$70-$7F` | 6 | enemy class |
| `$80-$FF` | 4 | default high tiles |

The table is exactly one page, so lookup is `LD L,tile; LD H,$6B; LD A,[HL]` while bank 13 is mapped. If hooks are placed in always-mapped WRAM and cannot cheaply bank-switch, copy the table once to a page-aligned 256-byte WRAM allocation and use that address instead. WRAM is preferable for interception latency, provided the allocation is audited against the game's state map.

## Cycle Savings Estimate

The current `hwoam_recolor` audit measures about 80T setup plus roughly 140–180T per active slot and 25T per empty slot:

| Frame | Current post-DMA sweep | Intercept work | VBlank saving |
|---|---:|---:|---:|
| Typical dungeon (12 active, 28 empty) | about 2,620T | about 12 × 80–130T in the main loop | about 2,620T |
| Busy boss frame (25 active, 15 empty) | about 4,375T | about 25 × 80–130T in the main loop | about 4,375T |
| Worst case (40 active) | about 5,680–7,280T plus setup | about 40 × 80–130T in the main loop | the full sweep cost |

The intercept is O(1) **per sprite emission**, not O(1) per frame: every changed sprite still needs one lookup. Its benefit is that it removes the O(40) scan and all empty-slot tests from the VBlank critical path and spreads work across the main loop. With a WRAM-resident LUT and a bank-0 trampoline, an 80–130T estimate per emitted sprite is realistic; bank switching to ROM bank 13 on every sprite would erase much of the saving and is not recommended.

Before implementation, validate the three semantic hooks with write watchpoints on C000-C09F during title, gameplay, transformations, bosses, death, pause, and ending. The acceptance criterion is that every non-clear write of an attribute byte is preceded in the same emitter invocation by its tile write and that C000 and C100 agree before DMA.
