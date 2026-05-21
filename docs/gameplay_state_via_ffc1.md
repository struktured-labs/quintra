# Gameplay Active Flag: FFC1

FFC1 is the **single most important game-state byte** for deciding
whether to run gameplay logic. It's the gate that subsystems read at
their entry to choose between menu/title behavior and gameplay behavior.

## Census

13 FFC1 read sites across the ROM:

| Bank | Addr   | Pattern after read              | Purpose                       |
|------|--------|---------------------------------|--------------------------------|
| 0    | 0x15C7 | `E0 DE AF E0 C1 ...`            | save+clear FFC1 (menu work)   |
| 0    | 0x19CB | `E0 DE AF E0 C1 ...`            | save+clear FFC1 (menu work)   |
| 0    | 0x1E6B | `18 EA`                         | branch on FFC1                |
| 0    | 0x34F5 | `CD A8 00 F0 94`                | route input via FFC1          |
| 1    | 0x4250 | `A7 28 03 CD 58 42`             | "if FFC1==0 skip; else CALL"  |
| 1    | 0x4781 | `A7 C8 13 13 C9`                | "if FFC1==0 return; else INC DE×2" |
| 1    | 0x478A | `A7 C8 1B 1B C9`                | same with DEC DE×2            |
| 1    | 0x4793 | `A7 C8 23 23 C9`                | same with INC HL×2            |
| 1    | 0x479C | `A7 C8 2B 2B C9`                | same with DEC HL×2            |
| 1    | 0x5122 | `A7 28 03 3E 10 D7`             | "if FFC1==0 skip; else RST 10"|
| 1    | 0x514C | `A7 28 03 3E 10 D7`             | (same pattern as 0x5122)      |
| 2    | 0x53CA | `B7 78 28 01 87 47`             | "if FFC1==0 skip combine"     |
| 2    | 0x53E4 | `B7 78 28 01 87 47`             | (same pattern as 0x53CA)      |

## Idiom patterns

The two dominant idioms are:

**Skip-if-not-gameplay**:
```asm
LDH A, (FFC1)
AND A          ; OR A
RET Z          ; if 0, return — this subsystem only runs in gameplay
; ... else body of gameplay logic ...
```

**Branch-on-gameplay**:
```asm
LDH A, (FFC1)
AND A
JR Z, +3       ; if 0, skip the next operation
LD A, 0x10     ; or similar gameplay-specific setup
RST 10
```

## What writes FFC1

The two save+clear sites at bank 0:0x15C7 and 0x19CB save FFC1 to FFDE,
clear it to 0, run menu code, then restore. So those are **menu
entries that temporarily suppress gameplay logic**.

## Connection to our v3.01 colorize handler

Our colorize_handler at bank 13 uses the same FFC1 gate:
```asm
LDH A, (FFC1); OR A; JR Z, +N   ; skip game-only stuff on menu/title
CALL 0xFF80                     ; OAM DMA
CALL shadow_main                ; OBJ colorizer
CALL attr_computation           ; build attr buffer
LD A, 1; LD (DF03), A           ; mark GDMA ready
```

So when FFC1=0 (menu/title), our colorize handler skips attr_computation
and only runs cond_pal + bg_sweep + GDMA-of-stale-buffer. When FFC1=1
(gameplay), the full pipeline runs.

This matches the rest of the ROM's gate idioms — FFC1 is THE flag for
"are we in gameplay right now".

## Subsystems that gate on FFC1

By the read sites, these bank-1 subsystems all check FFC1 first:
- 0x4250 (might be part of tile copy / scroll prep)
- 0x4781, 0x478A, 0x4793, 0x479C (4 entries for INC/DEC DE/HL — a
  pointer-mover helper family)
- 0x5122, 0x514C (RST 10 callers — pointer math helpers)

And bank-2 subsystems at 0x53CA, 0x53E4. Bank 0 has menu-related save/
clear sites.

## What this means for D880

D880 changes cause **music** changes. FFC1 changes cause **gameplay code**
changes. A scene transition (e.g., entering a boss arena) writes BOTH:

1. D880 = arena value (0x0C..0x14) → sound engine picks arena music
2. The arena entry routine activates new gameplay subsystems via
   their internal state bytes (FFBA level, FFBD room, etc.); FFC1
   stays at 1 throughout gameplay.

So D880 is part of the FULL story of "what state is the game in", but
**it's the audio side**, not the game-logic side. The game-logic side
is driven by FFC1 + many other per-subsystem flags.
