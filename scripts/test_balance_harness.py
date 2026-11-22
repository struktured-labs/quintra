#!/usr/bin/env python3
"""Emulator-free contracts for the human-skill balance harness.

* The Lua (mGBA whole-run) and Python (PyBoy slice) skill tiers stay equal.
* The Lua per-stage CSV header matches the number of fields it writes.
* The report generator computes the stage-3 boss and status-death gates
  correctly on a synthetic sweep, and --check fails when they are breached.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from balance_arena import FIELDS, PROFILES  # noqa: E402

LUA = (ROOT / "scripts/quintra_human_model.lua").read_text()


def lua_profiles() -> dict:
    start = LUA.index("QH_PROFILES = {") + len("QH_PROFILES = {")
    block = LUA[start:LUA.index("\n}\n", start)]
    out = {}
    marks = list(re.finditer(r"(\w+) =\s*\{", block))
    for i, mk in enumerate(marks):
        name = mk.group(1)
        body = block[mk.end():marks[i + 1].start() if i + 1 < len(marks) else len(block)]
        vals = {}
        for key, val in re.findall(r"(\w+)=(\{[^}]*\}|[0-9.]+)", body):
            vals[key] = (tuple(int(x) for x in re.findall(r"\d+", val))
                         if val.startswith("{") else float(val))
        out[name] = vals
    return out


def test_profiles_match():
    lua = lua_profiles()
    assert set(lua) == set(PROFILES), (set(lua), set(PROFILES))
    for tier, prof in PROFILES.items():
        for key, val in prof.items():
            got = lua[tier][key]
            want = tuple(val) if isinstance(val, tuple) else float(val)
            assert got == want, f"{tier}.{key}: lua {got} != python {want}"


def test_stage_header_matches_row():
    header = re.search(r'QH_STAGE_HEADER = "([^"]+)"', LUA).group(1).split(",")
    fmt = LUA[LUA.index("local function csv_row"):]
    fmt = re.search(r'string\.format\(\s*"([^"]+)"', fmt).group(1)
    assert len(fmt.split(",")) == len(header), (len(fmt.split(",")), len(header))


def synthetic(path: Path, s3_wins: int, status_deaths: int):
    rows = []
    for tier in ("average", "nonexpert"):
        for stage in range(1, 10):
            for seed in range(4):
                won = stage != 3 or seed < s3_wins
                died = not won
                rows.append(dict(
                    skill=tier, seed=seed, hero="corvin", **{"class": 2}, stage=stage,
                    kind="boss", difficulty="normal",
                    outcome="cleared" if won else "died", frames=3000 + stage * 100,
                    dmg_taken=8, dmg_dealt=60, hits=4, hp_start=14, hp_end=0 if died else 6,
                    hp_min=0 if died else 6, hp_max=14, boss_hp_start=60,
                    boss_hp_end=0 if won else 20, burst_max_2s=6, burst_spikes=1,
                    status_lands=1, status_harmful=1, status_in_boss=1, status_low_hp=0,
                    status_kinds="bleed:1",
                    death_status_kind="bleed" if died and seed < status_deaths else "",
                    death_status_age=60 if died and seed < status_deaths else -1,
                    death_status_active="", death_burst_2s=6 if died else 0,
                    missed_dodges=3, lapses=2))
                rows.append(dict(rows[-1], kind="entry", outcome="cleared", frames=1800,
                                 death_status_kind="", death_status_age=-1))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def run_report(tmp: Path, csv_path: Path, th: dict) -> tuple[int, dict]:
    th_path = tmp / "th.json"
    th_path.write_text(json.dumps(th))
    out = tmp / "report"
    res = subprocess.run([sys.executable, str(ROOT / "scripts/balance_report.py"), str(csv_path),
                          "--out", str(out), "--trials", "200", "--check", str(th_path)],
                         capture_output=True, text=True)
    assert (out / "report.md").exists(), res.stdout + res.stderr
    return res.returncode, json.loads((out / "metrics.json").read_text())


def test_report_gates():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        csv_path = tmp / "arena.csv"
        synthetic(csv_path, s3_wins=3, status_deaths=0)
        th = {"stage3_tier": "average", "stage3_boss_win_rate_min": 0.5,
              "status_death_share_max": 0.5, "status_min_deaths": 1}
        code, m = run_report(tmp, csv_path, th)
        assert code == 0, m
        assert abs(m["stage3_boss"]["average"]["win_rate"] - 0.75) < 1e-9
        synthetic(csv_path, s3_wins=1, status_deaths=4)
        code, m = run_report(tmp, csv_path, th)
        assert code == 1
        assert m["status_pooled"]["share"] == 1.0
        assert any(s["stage"] == 3 for s in m["spikes"])


if __name__ == "__main__":
    test_profiles_match()
    test_stage_header_matches_row()
    test_report_gates()
    print("[balance-harness] contracts OK")
