# mGBA Lua API capabilities (DMG/GB, mgba-qt 0.10.x)

Documented from iter 21 (2026-06-18). Probed against the installed
`mgba-qt` running the DX teleport ROM in offscreen mode.

## What works

| API | Notes |
|---|---|
| `emu.memory.cart0` | `mSTStruct` userdata. Use for ROM read/write that bypasses MBC. |
| `emu.memory.wram` | `mSTStruct`. WRAM read/write. |
| `emu.memory.oam` | `mSTStruct`. Use `:readRange(0, 0xA0)` for an atomic 40-slot OAM snapshot — preferred over `emu:readRange(0xFE00, 0xA0)`, which sees cross-region timing drift. |
| `emu.memory.vram` | `mSTStruct`. |
| `emu.memory.io` | `mSTStruct`. Read FF40 etc. |
| `emu:read8(addr)` / `emu:read16(addr)` | Standard generic read. `read8` on 0x0000-0x7FFF writes MBC regs — NOT ROM. Use `emu.memory.cart0:write8` to patch ROM. |
| `emu:write8(addr, val)` | Generic write. Same MBC caveat as read8. |
| `emu:setKeys(bitmask)` | Inject input. Bitmask: A=1, B=2, Sel=4, Start=8, R=0x10, L=0x20, U=0x40, D=0x80. Must call with 0 to release. |
| `emu:setWatchpoint(callback, addr, type)` | Watchpoint. **Signature is `(callback, addr, type)`**, NOT `(addr, type, callback)`. type=2 means write. |
| `callbacks:add("frame", fn)` | Per-frame hook. Standard. |
| `callbacks:add("keysRead", fn)` | Fires before joypad read — correct place for input injection. |
| `emu:stop()` | Pauses emulator (also stops the lua script's frame loop). |
| `emu:loadStateFile(path)` | Load a savestate from disk during a callback. |

## What does NOT work / does not exist

- `emu.cpu` — **nil**.
- `emu.getPC`, `emu.readPC` — **nil** (no PC access from Lua).
- `emu.registers` — **nil**.
- `emu.frame` — **nil** (track frame count yourself).
- `emu.memory.cart1`, `emu.memory.cartSram`, `emu.memory.iwram`, `emu.memory.cram` — **nil** for GB. (cart1 is for GBA cartridges; iwram/cram are GBA-specific.)

## setWatchpoint callback signature

The callback fires often, but the addr argument observed in iter 21 was a
`mSTTable` userdata — opaque, not a GB address number. Inspect the
table's keys to see if there's a `address` / `value` field; in practice
the API was unable to deliver "what address, what value, from which PC"
in the form needed for a write-source forensic probe.

**Consequence**: identifying the specific code site that writes to a
known OAM byte (e.g., the spider boss's `attr=0x01` writes to Sara slots
during minibosses) is NOT possible via headless mGBA Lua scripting alone.
It would require either:

- mGBA's GDB stub (`mgba -g <port>`) + a separate gdb session driven by
  a script that breakpoints on write to the address and reads PC,
- the mGBA debugger UI in interactive mode, or
- a build-time ROM scan combined with a PCS rebuild trace (find all
  `LD A,n; LD [HL],A` patterns where HL points into OAM, narrow by D880
  / FFBF guards).

## When to extend this doc

If a future mGBA version exposes `emu.cpu.pc` or makes the watchpoint
callback addr a number, update the "What works" section here and revive
the spider Sara-green forensic probe (which is currently blocked on this
limitation per `project_regression_harness_state.md`).
