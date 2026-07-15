#!/usr/bin/env python3
"""Position-based arena colorization (the "holy grail" path).

Tile-ID keying cannot reach zero alternation: a boss cell's tile flips between
boss-part and background as the boss animates, so a tile->palette table flips
the cell's color with it (and a shared tile bleeds the boss color onto the
background). The fix is **position keying**: a fixed per-cell palette map. Every
write of cell (r,c) writes the SAME value, so the attribute never flips — by
construction, regardless of the boss animation. The "bob" is an SCX/SCY scroll
shake (the boss footprint is stable in tilemap space), so a tilemap-space cell
map is bob-proof.

Pipeline:
  * parse_footprint_posmaps()  — footprint/posmap log -> 18x32 per-cell maps.
  * rle_encode_posmap()        — compress a map (highly repetitive) for ROM.
  * create_rle_expander()      — decompress one map -> WRAM 0xD000 (bank 2).
  * create_position_sweep()    — VBlank routine: on arena entry expand the
    active map to 0xD000 (lazy, once), then each frame copy a few rows from
    0xD000 to the BG attribute plane (cycling). Non-arena -> tail-call the
    normal tile-ID sweep.

Why a VBlank sweep (not STAT-wait, not GDMA): it runs inside the colorize
handler (VBlank IRQ) where all VRAM is writable (mode 1) and IME is off, so no
HBlank racing and FF70/VBK switches are safe. Plain CPU stores, no HDMA — so it
coexists with the arena's HBlank-HDMA scroll-shake (GDMA terminated that and
collapsed the arena; see docs/FINDINGS_2026_06_07_arena_gdma_isolation.md).

For zero alternation the inline hook's ATTR writes are neutralized in arenas
(tile-only) so this sweep is the sole attr writer there
(build_v301_gdma.create_inline_tile_copy_tileonly(arena_neutralize_d880=...)).

Compressed maps for all 9 arenas fit bank 13; expanding one to 0xD000 (the dead
GDMA buffer, bank 2) keeps the sweep's per-frame read a flat array.
"""
from pathlib import Path

POSMAP_ROWS = 18
POSMAP_COLS = 32          # tilemap stride
POSMAP_SIZE = POSMAP_ROWS * POSMAP_COLS   # 576 bytes
POSMAP_WRAM = 0xD000      # bank-2 WRAM scratch (dead GDMA buffer) for the
                          # expanded active-arena map


def parse_footprint_posmaps(log_path):
    """Parse a footprint/posmap log -> {boss_name: bytes(576)}.

    Lines:  ROW shalamar 0 00000004444444444444
    (20 base-10 palette digits per visible column). Missing rows -> all 0.
    Cols 20..31 are off-screen -> 0.
    """
    rows = {}
    for line in Path(log_path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "ROW":
            name, r, digits = parts[1], int(parts[2]), parts[3]
            rows.setdefault(name, {})[r] = digits
    maps = {}
    for name, rd in rows.items():
        m = bytearray(POSMAP_SIZE)
        for r in range(POSMAP_ROWS):
            d = rd.get(r, "")
            for c in range(min(20, len(d))):
                ch = d[c]
                m[r * POSMAP_COLS + c] = (int(ch) & 7) if ch.isdigit() else 0
        maps[name] = bytes(m)
    return maps


def rle_encode_posmap(m):
    """Run-length encode a 576-byte posmap as (count, value) pairs.

    count is 1..255, value 0..7. Runs sum to exactly 576 so the expander can
    stop when the destination pointer reaches D000+576 (no terminator).
    """
    out = bytearray()
    i = 0
    n = len(m)
    while i < n:
        v = m[i]
        run = 1
        while i + run < n and m[i + run] == v and run < 255:
            run += 1
        out += bytes([run, v & 7])
        i += run
    return bytes(out)


# ----------------------------------------------------------------------
# Tiny relative-jump assembler (mirrors build_v301_gdma's style)
# ----------------------------------------------------------------------
class _Asm:
    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fwd = []

    def db(self, *bs):
        for b in bs:
            if isinstance(b, (list, bytes, bytearray)):
                self.code.extend(b)
            else:
                self.code.append(b & 0xFF)
        return self

    def label(self, name):
        self.labels[name] = len(self.code)
        return self

    def jr(self, opcode, name):
        if name in self.labels:
            off = self.labels[name] - (len(self.code) + 2)
            assert -128 <= off <= 127, f"JR {name} out of range: {off}"
            self.db(opcode, off & 0xFF)
        else:
            self.db(opcode, 0x00)
            self.fwd.append((len(self.code) - 1, name))
        return self

    def finish(self):
        for pos, name in self.fwd:
            off = self.labels[name] - (pos + 1)
            assert -128 <= off <= 127, f"fwd JR {name} out of range: {off}"
            self.code[pos] = off & 0xFF
        return bytes(self.code)


def create_rle_expander(posmap_wram=POSMAP_WRAM, total=POSMAP_SIZE):
    """Decompress an RLE posmap (HL = ptr, bank-13 ROM) into WRAM bank 2 at
    posmap_wram. Sets FF70=2 for the write, restores FF70=1. IME is off
    (VBlank handler), so no DI/EI needed. Clobbers A,C,DE,HL; preserves B.
    """
    end = posmap_wram + total
    a = _Asm()
    a.db(0x3E, 0x02, 0xE0, 0x70)                 # LD A,2; LDH [FF70],A
    a.db(0x11, posmap_wram & 0xFF, (posmap_wram >> 8) & 0xFF)  # LD DE, D000
    a.label('loop')
    a.db(0x2A)                                    # LD A,[HL+]  (count)
    a.db(0x4F)                                    # LD C,A
    a.db(0x2A)                                    # LD A,[HL+]  (value)
    a.label('inner')
    a.db(0x12, 0x13)                              # LD [DE],A; INC DE
    a.db(0x0D)                                    # DEC C
    a.jr(0x20, 'inner')                          # JR NZ, inner
    a.db(0x7A, 0xFE, (end >> 8) & 0xFF)           # LD A,D; CP end_hi
    a.jr(0x20, 'loop')                           # JR NZ, loop
    a.db(0x7B, 0xFE, end & 0xFF)                  # LD A,E; CP end_lo
    a.jr(0x20, 'loop')                           # JR NZ, loop
    a.db(0x3E, 0x01, 0xE0, 0x70)                 # LD A,1; LDH [FF70],A
    a.db(0xC9)                                    # RET
    return a.finish()


def create_position_sweep(possweep_addr, orig_sweep_addr, rle_ptr_table_addr,
                          expand_addr, row_cursor_addr=0xDF40,
                          flag_addr=0xDF46, scratch_addr=0xDF47,
                          rows_per_frame=2, posmap_wram=POSMAP_WRAM):
    """VBlank position sweep with lazy per-arena RLE expansion.

    Dispatch: idx = D880-0x0C. Non-arena -> clear flag, JP orig_sweep.
    Arena: if flag != idx+1, look up rle_ptr_table[idx]; 0 -> fallback (JP
    orig_sweep); else CALL expander (fills D000 bank 2), flag=idx+1, cursor=0.
    Then copy rows_per_frame rows (32 bytes each) D000->VRAM attr plane,
    cycling row_cursor 0..17, FF70=2 while reading D000.

    Scratch (free DF region): row_cursor_addr (cursor), flag_addr (expanded
    idx+1), scratch_addr (vram_hi), scratch_addr+1 (rows_left).
    """
    a = _Asm()
    ol, oh = orig_sweep_addr & 0xFF, (orig_sweep_addr >> 8) & 0xFF
    el, eh = expand_addr & 0xFF, (expand_addr >> 8) & 0xFF
    ptl, pth = rle_ptr_table_addr & 0xFF, (rle_ptr_table_addr >> 8) & 0xFF
    rc_l, rc_h = row_cursor_addr & 0xFF, (row_cursor_addr >> 8) & 0xFF
    fl_l, fl_h = flag_addr & 0xFF, (flag_addr >> 8) & 0xFF
    vhi, sc_h = scratch_addr & 0xFF, (scratch_addr >> 8) & 0xFF
    rleft = (scratch_addr + 1) & 0xFF
    pm_hi = (posmap_wram >> 8) & 0xFF      # D000 low byte assumed 0

    # --- dispatch ---
    a.db(0xFA, 0x80, 0xD8)           # LD A,[D880]
    a.db(0xD6, 0x0C)                 # SUB 0x0C
    a.jr(0x38, 'normal')            # JR C, normal
    a.db(0xFE, 0x09)                # CP 9
    a.jr(0x30, 'normal')            # JR NC, normal
    a.jr(0x18, 'arena')            # JR arena
    a.label('normal')
    a.db(0xAF, 0xEA, fl_l, fl_h)     # XOR A; LD [flag],A   (clear in non-arena)
    a.db(0xC3, ol, oh)               # JP orig_sweep

    # --- arena: A = idx ---
    a.label('arena')
    a.db(0x47)                       # LD B,A          (B = idx)
    a.db(0x3C)                       # INC A
    a.db(0x4F)                       # LD C,A          (C = want = idx+1)
    a.db(0xFA, fl_l, fl_h)           # LD A,[flag]
    a.db(0xB9)                       # CP C
    a.jr(0x28, 'copy')              # JR Z, copy      (already expanded)
    # not expanded: HL = rle_ptr_table + idx*2
    a.db(0x78, 0x87)                 # LD A,B; ADD A,A (idx*2)
    a.db(0x21, ptl, pth)             # LD HL, table
    a.db(0x85, 0x6F)                 # ADD A,L; LD L,A
    a.db(0x30, 0x01, 0x24)           # JR NC,+1; INC H
    a.db(0x2A, 0x5F)                 # LD A,[HL+]; LD E,A   (rle_lo)
    a.db(0x7E, 0x57)                 # LD A,[HL];  LD D,A   (rle_hi) -> DE=ptr
    a.db(0x7B, 0xB2)                 # LD A,E; OR D
    a.jr(0x20, 'have')              # JR NZ, have
    a.db(0xAF, 0xEA, fl_l, fl_h)     # XOR A; LD [flag],A  (no map)
    a.db(0xC3, ol, oh)               # JP orig_sweep  (fallback)
    a.label('have')
    a.db(0x62, 0x6B)                 # LD H,D; LD L,E  (HL = rle ptr)
    a.db(0xCD, el, eh)               # CALL expander   (fills D000; B preserved)
    a.db(0x78, 0x3C)                 # LD A,B; INC A   (want)
    a.db(0xEA, fl_l, fl_h)           # LD [flag],A
    a.db(0xAF, 0xEA, rc_l, rc_h)     # XOR A; LD [row_cursor],A

    # --- copy phase ---
    a.label('copy')
    a.db(0xF0, 0x40, 0xE6, 0x08)     # LDH A,[FF40]; AND 8
    a.jr(0x28, 'use98')
    a.db(0x3E, 0x9C)
    a.jr(0x18, 'haveH')
    a.label('use98')
    a.db(0x3E, 0x98)
    a.label('haveH')
    a.db(0xEA, vhi, sc_h)            # [vhi] = vram base hi
    a.db(0x3E, rows_per_frame & 0xFF)
    a.db(0xEA, rleft, sc_h)          # [rows_left]
    # Scratch (cursor/vhi/rows_left) lives in switchable WRAM (DF..), so it must
    # be touched with FF70=1. Set FF70=2 ONLY around the 32-byte D000 read (VRAM
    # writes use VBK, which is bank-independent), and restore before any scratch
    # access. (Bug fixed here: FF70=2 spanning the scratch reads hit bank 2 ->
    # garbage cursor/rows_left -> runaway VRAM writes -> arena freeze.)
    a.label('rowloop')
    a.db(0xFA, rc_l, rc_h)           # A=[row_cursor]   (FF70=1)
    a.db(0x6F, 0x26, 0x00)           # L=A; H=0
    a.db(0x29, 0x29, 0x29, 0x29, 0x29)  # HL = row*32  (offset)
    a.db(0x44, 0x4D)                 # B=H; C=L   (offset)
    # src DE = D000 + offset
    a.db(0x79, 0x5F)                 # LD A,C; LD E,A
    a.db(0x78, 0xC6, pm_hi, 0x57)    # LD A,B; ADD 0xD0; LD D,A
    # dst HL = vram_base + offset
    a.db(0x60, 0x69)                 # H=B; L=C   (offset)
    a.db(0xFA, vhi, sc_h)            # A=[vhi]    (FF70=1)
    a.db(0x84, 0x67)                 # ADD H; LD H,A
    # copy 32 bytes D000(bank2) -> VRAM(VBK1)
    a.db(0x3E, 0x01, 0xE0, 0x4F)     # VBK=1
    a.db(0x3E, 0x02, 0xE0, 0x70)     # FF70=2  (D000 readable)
    a.db(0x06, 0x20)                 # B=32
    a.label('cp')
    a.db(0x1A, 0x22, 0x13, 0x05)     # LD A,[DE]; LD [HL+],A; INC DE; DEC B
    a.jr(0x20, 'cp')
    a.db(0x3E, 0x01, 0xE0, 0x70)     # FF70=1  (restore before scratch)
    a.db(0xAF, 0xE0, 0x4F)           # VBK=0
    # advance row_cursor (0..17 wrap)
    a.db(0xFA, rc_l, rc_h, 0x3C)     # A=[cursor]; INC A
    a.db(0xFE, 0x12)                 # CP 18
    a.jr(0x20, 'nowrap')
    a.db(0xAF)
    a.label('nowrap')
    a.db(0xEA, rc_l, rc_h)           # [cursor]=A
    a.db(0xFA, rleft, sc_h, 0x3D)    # A=[rows_left]; DEC A
    a.db(0xEA, rleft, sc_h)
    a.jr(0x20, 'rowloop')
    a.db(0xC9)                       # RET (FF70 already 1)
    return a.finish()
