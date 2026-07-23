#!/usr/bin/env python3
"""Contract: periodic trainer states stay current, distinct, and loadable."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from quintra_pyboy_env import QuintraPyBoyEnv


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
SOURCE = ROOT / "tmp/stage-states/quintra-stage-04-entry-wolfkin-easy.pyboy"


def main() -> None:
    assert SOURCE.exists(), "stage-state curriculum is missing"
    with tempfile.TemporaryDirectory(prefix="quintra-timed-contract-") as temp:
        out = Path(temp)
        subprocess.run([
            sys.executable, str(ROOT / "scripts/run_pyboy_checkpoints.py"),
            "--rom", str(ROM), "--out", str(out), "--state", str(SOURCE),
            "--total-frames", "36", "--checkpoint-frames", "4",
        ], check=True, capture_output=True, text=True)
        manifest = json.loads((out / "manifest.json").read_text())
        records = manifest["states"]
        assert manifest["stall_advance_enabled"] is True
        assert manifest["policy_sha256"] == hashlib.sha256(
            (ROOT / "scripts/run_pyboy_checkpoints.py").read_bytes()).hexdigest()
        assert manifest["source_state_sha256"] == hashlib.sha256(
            SOURCE.read_bytes()).hexdigest()
        assert manifest["curriculum_advances"] >= 2
        assert len(records) >= 3
        assert [record["stage"] for record in records[:3]] == [4, 5, 6]
        assert len({record["room_counter"] for record in records[:3]}) == 3
        assert [record["curriculum_advance"] for record in records[:3]] \
            == [None, 5, 6]

        env = QuintraPyBoyEnv(ROM)
        try:
            restored = [env.load_state(out / record["file"])
                        for record in records[:3]]
        finally:
            env.close()
        assert [obs["stage"] for obs in restored] == [4, 5, 6]
        assert all(obs["difficulty"] == "easy" for obs in restored)
        assert all(obs["class_id"] == 0 and obs["hp"] > 0 for obs in restored)

    print("[timed-states] PASS current manifest + distinct stage 4/5/6 "
          "curriculum fallbacks")


if __name__ == "__main__":
    main()
