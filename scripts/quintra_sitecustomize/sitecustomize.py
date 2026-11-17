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

        def _quintra_mark_seen(self):
            # Only touch WRAM bank 0 (run_state). loop_current_screen and
            # room_start_vignette live in switchable 0xD000, so a mid-fight
            # SVBK change would make a screen read look like VIGNETTE and
            # inject START, or clobber the wrong byte.
            if os.environ.get("QUINTRA_KEEP_VIGNETTES") == "1":
                return
            syms = self._quintra_load_syms()
            if not syms or not syms.get("seen"):
                return
            try:
                self.memory[syms["seen"]] = 0xFF
                self.memory[syms["seen"] + 1] = 0xFF
            except Exception:
                return

        def tick(self, *args, **kwargs):
            # Split tick(n) so a boot_room-style tick(90) cannot run
            # run_state_init, the one-frame delay, and the foyer arm in
            # one host call (seen would be cleared then armed unobserved).
            if os.environ.get("QUINTRA_KEEP_VIGNETTES") == "1":
                return super().tick(*args, **kwargs)
            count = 1
            rest = args
            if args and isinstance(args[0], int):
                count = args[0]
                rest = args[1:]
            result = None
            for _ in range(max(1, count)):
                result = super().tick(1, *rest, **kwargs)
                self._quintra_mark_seen()
            return result

    _pyboy_mod.PyBoy = _PyBoy
    _pyboy_mod._quintra_mute_wrapped = True
