# Penta Dragon DX Game State Machine

The game's runtime state is encoded across 5 bytes that drive
behavior and transitions. This document maps them and their typical
interactions during gameplay.

## State bytes

| Byte | Range | Meaning |
|---|---|---|
| **D880** | 0x00-0x18 | Master scene state (boot, dungeon, mini-boss, boss arenas, death) |
| **FFC1** | 0/1 | Gameplay-active flag (0 = title/menu, 1 = dungeon or arena) |
| **FFBA** | 0-8 | Level / boss counter; indexes the arena jump table at bank 2:0x6EA6 |
| **FFBF** | 0-N | Mini-boss / stage boss flag (0 = none, 1+ = active) |
| **FFBD** | 1-7 | Current room within dungeon (room transition table at 0x0BBF) |

## D880 values (full table)

| D880 | Meaning |
|---|---|
| 0x00 | Stuck / uninitialized / inter-state transition |
| 0x01 | Title screen / boot splash |
| 0x02 | Dungeon (normal gameplay) |
| 0x0A | Mini-boss combat (Haunt Dragon / Arachnid) |
| 0x0B | Mini-boss splash / boss splash |
| 0x0C | Boss arena: Shalamar |
| 0x0D | Boss arena: Riff |
| 0x0E | Boss arena: Crystal Dragon |
| 0x0F | Boss arena: Cameo |
| 0x10 | Boss arena: Ted |
| 0x11 | Boss arena: Troop |
| 0x12 | Boss arena: Faze |
| 0x13 | Boss arena: Penta Dragon (final main) |
| 0x14 | Boss arena: Hidden boss (Angela?) |
| 0x17 | Death / timeout cinematic |
| 0x18 | Boss splash (stage transition / stage load) |

## Typical transition timeline (autoplay trace)

From a mGBA trace over 4000 frames with simple keystroke autoplay:

```
f1-11      D880=0x00  FFC1=0  FFBA=0  FFBF=0  FFBD=0   (boot uninit)
f12-195    D880=0x01  FFC1=0  FFBA=0  FFBF=0  FFBD=0   (publisher splash YANOMAN)
f196-307   D880=0x00  FFC1=0  FFBA=0  FFBF=0  FFBD=0   (title screen menu)
f308       D880=0x00  FFC1=1  FFBA=0  FFBF=0  FFBD=5   (START pressed → enter game)
f335       D880=0x18  FFC1=1  FFBA=0  FFBF=0  FFBD=5   (STAGE LOAD splash)
f796       D880=0x02  FFC1=1  FFBA=0  FFBF=0  FFBD=5   (entered dungeon room 5)
f987       D880=0x02  FFC1=1  FFBA=0  FFBF=0  FFBD=3   (transitioned to room 3)
f1025      D880=0x02  FFC1=1  FFBA=0  FFBF=0  FFBD=1   (room 1)
...continues alternating 1↔3↔5↔7 as autoplay walks around...
```

## Authority chain

```
FFB7 (HRAM mirror)
  ↑
  └── FFB7 is written alongside D880 by boss arena routines (mirror).
      Some game code may check FFB7 instead of D880 for state.

D880 (master scene state, WRAM)
  ↑
  ├── Written by: boss arena routines (bank 2:0x886E onwards) at entry
  │   Each arena's first instructions are `LD A, val; LD [D880], A`.
  ├── Written by: scene transition logic (bank 1:0x158C... cf 02 etc.
  │   the "publisher" mechanism via FFB7 mirroring)
  └── Read by: many subsystems for state-dependent behavior

FFC1 (gameplay-active flag, HRAM)
  ↑
  ├── 0 during title screen, menu, and splash transitions.
  ├── Set to 1 when game enters playable state (dungeon or arena).
  └── Read by colorize handler to gate work (bg_sweep, OAM DMA, OBJ colorize).

FFBA (level counter, HRAM)
  ↑
  ├── Increments when player kills a stage boss.
  ├── Indexes boss arena jump table at bank 2:0x6EA6 to dispatch
  │   the correct arena setup routine.
  └── Used by save / checkpoint to record progress.

FFBF (mini-boss / boss flag, HRAM)
  ↑
  ├── 0 = no boss active.
  ├── 1 = Gargoyle (Haunt Dragon mini-boss, FFBA=0).
  ├── 2 = Arachnid (Spider mini-boss, FFBA=0).
  ├── 3+ = various bosses (FFBA-indexed dispatch via different path).
  └── cond_pal includes FFBF in its hash; FFBF changes trigger
      palette re-load (which loads boss palette into OBJ slot N
      via the slot×8 fix).

FFBD (current room, HRAM)
  ↑
  ├── Range 1-7 during dungeon.
  ├── Room transition table at 0x0BBF maps current room + edge → next room.
  ├── Dispatch table at bank 1:0x4481 dispatches room-specific behavior.
  └── Read by: room scrolling, enemy spawn tables.
```

## Common transitions

| From | To | Trigger |
|---|---|---|
| Boot (D880=0x00) | Title (D880=0x01) | First VBlank after CGB init |
| Title (D880=0x01) | Pre-game (D880=0x00, FFC1=1) | START pressed |
| Pre-game | Stage splash (D880=0x18) | Stage selection / fall-through |
| Stage splash | Dungeon (D880=0x02) | Splash timeout (~460 frames) |
| Dungeon | Mini-boss arena (D880=0x0A) | DCB8 cycle hits miniboss section |
| Mini-boss | Dungeon (D880=0x02) | Mini-boss defeated |
| Dungeon | Boss arena (D880=0x0C..0x14) | Boss spawn via FFBA-indexed dispatch |
| Boss arena | Death (D880=0x17) | DCBB → 0 (HP depleted) |
| Death | Title (D880=0x01) | Continue / game over |

## State publisher mechanism

Boss arena routines self-publish state on entry:
```
LD A, arena_id    ; e.g. 0x0C for Shalamar
LD [D880], A      ; → master scene state
LDH [FFB7], A     ; → HRAM mirror
```

This sets BOTH D880 (WRAM) and FFB7 (HRAM) to the arena ID. Game
code reads either depending on whether it's in a fast-path (HRAM)
or a slow-path (WRAM). Both stay in sync.

## How v3.01's cond_pal interacts

`cond_pal_addr` (bank 13:0x6C90) computes a hash:
```
B = FFBE ^ FFBF ^ FFC0 ^ FFD0 ^ FFC1 ^ FFBD + 1
```

If hash differs from previous (stored in DF00), full palette_loader
runs (writes 64 BG + 64 OBJ + boss palette to CRAM). Otherwise RETs
to skip ~2800T of palette writes per VBlank.

This means palette_loader runs on every state transition that changes
ANY of the hashed bytes. Boss spawn (FFBF changes) → reload. Room
change (FFBD changes) → reload. Mini-boss form change (FFBE) → reload.
