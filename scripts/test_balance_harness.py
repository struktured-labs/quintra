#!/usr/bin/env python3
"""Emulator-free contracts for the human-skill balance harness.

* The Lua (mGBA whole-run) and Python (PyBoy slice) skill tiers stay equal.
* The Lua per-stage CSV header matches the number of fields it writes.
* The report generator computes the stage-3 boss and status-death gates
  correctly on a synthetic sweep, and --check fails when they are breached.
* The room report computes status-death lift against fight time and the
  plain-hit control, ignores a proc on the killing blow, and gates on lift.
* The room pilot never walks out through a door.
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


def synthetic_rooms(path: Path, killing_blow_proc: bool):
    """Ten stage-3 average fights; five die 2 s after a Burn lands."""
    from balance_rooms import EVENT_FIELDS, FIGHT_FIELDS
    rows, events = [], []
    for seed in range(10):
        died = seed < 5
        frames = 6000
        base = dict(skill="average", seed=seed, hero="corvin", stage=3, difficulty="normal",
                    room_id=40, fixture=f"room-s03-corvin-normal-{seed:02d}.pyboy")
        rows.append(dict(base, **{"class": 2}, enemy_kinds="14 25", cinder=1,
                         outcome="died" if died else "cleared", frames=frames, hits=3,
                         dmg_taken=14 if died else 4, dot_dmg=0, hp_start=14, hp_end=0 if died else 10,
                         hp_min=0 if died else 10, hp_max=14, lands=1, harmful=1, unreachable=0,
                         exposed5=300, exposed10=600, death_kind="burn" if died else "",
                         death_age=120 if died else -1, death_chain=""))
        blank = {k: "" for k in EVENT_FIELDS}

        def ev(frame, event, **kw):
            events.append(dict(blank, **base, frame=frame, event=event, hp=kw.pop("hp", 8),
                               hp_max=14, **kw))
        ev(1000, "hit", carrier="", procced=0)
        land = frames - 120 if died else 1000
        ev(land - 1, "hit", carrier="burn", procced=1)
        ev(land, "status", kind="burn", hp=6, crowd=1, hazard_near=0)
        if died:
            ev(frames, "hit", carrier="", procced=0, hp=0)
            if killing_blow_proc and seed == 0:
                ev(frames, "status", kind="stop", hp=0, crowd=1, hazard_near=0)
            ev(frames, "death", kind="burn")
    for p_, fields, data in ((path, FIGHT_FIELDS, rows),
                             (path.with_suffix(".events.csv"), EVENT_FIELDS, events)):
        with p_.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)


def test_room_report():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        csv_path = tmp / "rooms-normal.csv"
        synthetic_rooms(csv_path, killing_blow_proc=True)
        th = {"rooms": {"tier": "average", "min_deaths": 4, "lift10_max_normal": 100.0}}
        (tmp / "th.json").write_text(json.dumps(th))
        cmd = [sys.executable, str(ROOT / "scripts/balance_rooms_report.py"), str(csv_path),
               "--out", str(tmp / "rep"), "--check", str(tmp / "th.json")]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr
        m = json.loads((tmp / "rep/rooms-metrics.json").read_text())["normal"]
        l10 = m["stages_1_3_tier"]["average"]["lift10"]
        # 5/5 deaths sit 2 s after a Burn (the Stop on the killing blow is
        # ignored). 10 s windows: five full (597 frames) plus five cut to
        # 120 frames by the death, over 60000 fight frames.
        exposure = (5 * 597 + 5 * 120) / 60000
        assert l10["near"] == 5 and l10["deaths"] == 5, l10
        assert abs(l10["exposure"] - exposure) < 1e-9, l10
        assert abs(l10["lift"] - 1 / exposure) < 1e-6, l10
        burn = m["all"]["status"]["burn"]
        assert burn["proc"] == 1.0 and burn["lands"] == 10 and burn["hp_med"] == 3.0, burn
        assert m["cinder"]["outcome"]["fights"] == 10
        th["rooms"]["lift10_max_normal"] = 10.0
        (tmp / "th.json").write_text(json.dumps(th))
        assert subprocess.run(cmd, capture_output=True, text=True).returncode == 1


def test_pilot_keeps_inside():
    from balance_rooms import keep_inside
    obs = dict(x=4, y=60, world_width=248, world_height=248)
    assert keep_inside(obs, 0x08 | 0x10) == 0x10        # no LEFT out the west door
    assert keep_inside(dict(obs, x=230), 0x02) == 0       # no RIGHT out the east door
    assert keep_inside(dict(obs, x=120, y=230), 0x04 | 0x02) == 0x02
    assert keep_inside(dict(obs, x=120, y=120), 0x0F) == 0x0F


if __name__ == "__main__":
    test_profiles_match()
    test_stage_header_matches_row()
    test_report_gates()
    test_room_report()
    test_pilot_keeps_inside()
    print("[balance-harness] contracts OK")
