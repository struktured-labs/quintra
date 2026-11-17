"""Auto-mute Quintra start vignettes in PyBoy tests.

A new run plays the stage 1 foyer vignette on the first room tick. Live-ROM
contracts that only want gameplay after class select would otherwise land on
SCREEN_VIGNETTE. This hook marks every vignette seen (and clears the queued
foyer flag) as soon as run_state exists, between PyBoy frames.

test_stage_vignettes.py sets QUINTRA_KEEP_VIGNETTES=1 to opt out.
A cart copied into a temp dir without its .noi still resolves symbols
from rom/working/quintra.noi in the worktree.
"""
import os
import re
from pathlib import Path

try:
    import pyboy as _pyboy_mod
except Exception:
    _pyboy_mod = None

if _pyboy_mod is not None and not getattr(_pyboy_mod, "_quintra_mute_wrapped", False):
    _Orig = _pyboy_mod.PyBoy

    class _PyBoy(_Orig):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._quintra_muted = os.environ.get("QUINTRA_KEEP_VIGNETTES") == "1"
            self._quintra_syms = None
            rom = args[0] if args else kwargs.get("gamerom") or kwargs.get("filename")
            self._quintra_rom = str(rom) if rom else None

        def _quintra_find_noi(self, rom):
            """Temp cart copies often omit the .noi next to the .gbc."""
            if rom:
                p = Path(rom).with_suffix(".noi")
                if p.exists():
                    return p
                stem = Path(rom).stem + ".noi"
            else:
                stem = "quintra.noi"
            candidates = []
            here = Path.cwd().resolve()
            for parent in (here, *here.parents):
                candidates.append(parent / "rom" / "working" / stem)
                candidates.append(parent / "rom" / "working" / "quintra.noi")
                if (parent / "src" / "game").is_dir():
                    break
            for c in candidates:
                if c.exists():
                    return c
            return None

        def _quintra_load_syms(self):
            if self._quintra_syms is not None:
                return self._quintra_syms
            rom = self._quintra_rom
            noi_path = self._quintra_find_noi(rom)
            if not noi_path:
                self._quintra_syms = False
                return False
            text = noi_path.read_text()

            def sym(name):
                m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", text)
                return int(m.group(1), 16) if m else None

            self._quintra_syms = {
                "screen": sym("_loop_current_screen"),
                "seen": (sym("_run_state") or 0) + 60,
                "pending": sym("_room_start_vignette"),
            }
            return self._quintra_syms

        def _quintra_maybe_mute(self):
            if self._quintra_muted:
                return
            if os.environ.get("QUINTRA_KEEP_VIGNETTES") == "1":
                self._quintra_muted = True
                return
            syms = self._quintra_load_syms()
            if not syms or not syms.get("screen"):
                return
            try:
                scr = self.memory[syms["screen"]]
            except Exception:
                return
            # 3 = RUN_INIT, 5 = ROOM, 6 = VIGNETTE
            if scr not in (3, 5, 6):
                return
            try:
                self.memory[syms["seen"]] = 0xFF
                self.memory[syms["seen"] + 1] = 0xFF
                if syms.get("pending") is not None:
                    self.memory[syms["pending"]] = 0
            except Exception:
                return
            self._quintra_muted = True

        def tick(self, *args, **kwargs):
            # Mute between frames so a batched tick(90) cannot skip past RUN_INIT.
            if self._quintra_muted:
                return super().tick(*args, **kwargs)
            count = 1
            if args and isinstance(args[0], int):
                count = args[0]
                args = args[1:]
            result = None
            for _ in range(max(1, count)):
                result = super().tick(1, *args, **kwargs)
                self._quintra_maybe_mute()
                if self._quintra_muted and count > 1:
                    left = count - 1 - _
                    # After mute, finish the batch in one call if any remain.
                    # The loop already completed this frame; remaining are left-1?
                    # We ran (_+1) frames so far; remaining = count - (_+1)
                    remain = count - (_ + 1)
                    if remain > 0:
                        result = super().tick(remain, *args, **kwargs)
                    break
            return result

    _pyboy_mod.PyBoy = _PyBoy
    _pyboy_mod._quintra_mute_wrapped = True
