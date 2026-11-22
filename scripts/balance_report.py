#!/usr/bin/env python3
"""Per-stage difficulty report and balance gate for Quintra.

Reads the human-skill slice CSV from scripts/balance_arena.py (and,
optionally, the whole-run stages.csv from scripts/balance_sweep.py), and
writes a markdown report, a per-stage CSV, and a metrics JSON:

  * Stage 3 boss panel: win rate and time-to-kill per tier, burst damage.
  * Status panel: harmful status landings during bosses / at low HP, and the
    share of deaths that follow a status within N seconds, by effect & stage.
  * Difficulty curve, stages 1-9, per tier: median with p25/p75.
  * Spikes: stages whose loss rate or time jumps past K x their neighbours.
  * Estimated human first-clear time per tier (death wipes the run), with
    the share of that time inside Steam's 2-hour refund window.

`--check thresholds.json` exits 1 when a gate fails (used by CI).
Every modelled number is an estimate; see the spec for the assumptions.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
TIERS = ("nonexpert", "average", "skilled", "bot")
FPS = 59.7275
STATUS_WINDOWS_S = (3, 5, 10)
REFUND_WINDOW_MIN = 120

# Whole-stage composition assumptions (estimates; replace with telemetry).
DETOUR_FACTOR = 1.6        # mission objectives + exploration vs shortest path
TRANSIT_S = 12             # walking a cleared/empty room, door to door
RIFTWILD_LEG_S = {"nonexpert": 240, "average": 180, "skilled": 120, "bot": 90}
PUZZLES_PER_STAGE = 1.5
RESTART_OVERHEAD_S = 45    # game over, title, hero select, foyer
LEARNING_RATE = 0.10       # per visit to a stage, move toward the next tier up


def q(values, p):
    if not values:
        return float("nan")
    v = sorted(values)
    k = (len(v) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if v[lo] == v[hi] or not (math.isfinite(v[lo]) and math.isfinite(v[hi])):
        return v[hi] if k - lo >= 0.5 else v[lo]
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def clean(x):
    """JSON-safe copy: NaN/inf become null."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def fmt(x, nd=1):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def band(values, nd=1, scale=1.0):
    if not values:
        return "n/a"
    s = [v * scale for v in values]
    return f"{fmt(q(s, .5), nd)} ({fmt(q(s, .25), nd)}-{fmt(q(s, .75), nd)})"


def rate(k, n):
    return (k / n) if n else float("nan")


def smoothed(k, n):
    """Jeffreys-smoothed probability so 0/4 is not treated as impossible."""
    return (k + 0.5) / (n + 1)


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def num(r, k):
    try:
        return float(r[k])
    except (KeyError, ValueError):
        return float("nan")


def critical_path_rooms(stage: int) -> float:
    """Mean seeded entry->Colossus maze distance in rooms (topology mirror)."""
    try:
        from quintra_topology import (dungeon_distances_from, dungeon_entry_cell,
                                      dungeon_size)
    except Exception:
        return 7.0
    rng = random.Random(stage)
    total = 0
    n = 60
    size = dungeon_size(stage - 1)
    for _ in range(n):
        seed = rng.getrandbits(32)
        entry = dungeon_entry_cell(size, seed, stage - 1)
        dist = dungeon_distances_from(size, seed, stage - 1, entry)
        total += dist.get(size - 1, 7)
    return total / n


class Stats:
    def __init__(self, rows):
        self.rows = rows
        self.by = defaultdict(list)
        for r in rows:
            self.by[(r["skill"], int(r["stage"]), r["kind"])].append(r)

    def get(self, tier, stage, kind):
        return self.by.get((tier, stage, kind), [])


def boss_summary(rs):
    n = len(rs)
    wins = [r for r in rs if r["outcome"] == "cleared"]
    deaths = [r for r in rs if r["outcome"] == "died"]
    return {
        "n": n, "wins": len(wins), "win_rate": rate(len(wins), n),
        "deaths": len(deaths), "timeouts": n - len(wins) - len(deaths),
        "ttk_s": [num(r, "frames") / FPS for r in wins],
        "attempt_s": [num(r, "frames") / FPS for r in rs],
        "dmg": [num(r, "dmg_taken") for r in rs],
        "burst": [num(r, "burst_max_2s") for r in rs],
        "burst_frac": [num(r, "burst_max_2s") / max(1, num(r, "hp_max")) for r in rs],
        "spikes": [num(r, "burst_spikes") for r in rs],
        "boss_hp_left": [num(r, "boss_hp_end") / max(1, num(r, "boss_hp_start"))
                         for r in rs if r["outcome"] != "cleared" and num(r, "boss_hp_start") > 0],
        "status_in_boss": sum(num(r, "status_in_boss") for r in rs),
        "status_low_hp": sum(num(r, "status_low_hp") for r in rs),
        "status_harmful": sum(num(r, "status_harmful") for r in rs),
        "minutes": sum(num(r, "frames") for r in rs) / FPS / 60,
        # Continuous progress: share of the Colossus's HP removed (1 = kill).
        "progress": [1.0 if r["outcome"] == "cleared" else
                     1 - num(r, "boss_hp_end") / num(r, "boss_hp_start")
                     for r in rs if num(r, "boss_hp_start") > 0],
    }


def room_summary(rs):
    # A room the pilot cannot finish in 60 s (it got lost, not killed) says
    # nothing about danger; count it as harness health, not as survival.
    timeouts = sum(r["outcome"] == "timeout" for r in rs)
    rs = [r for r in rs if r["outcome"] in ("cleared", "died")]
    n = len(rs)
    deaths = [r for r in rs if r["outcome"] == "died"]
    return {
        "n": n, "deaths": len(deaths), "death_rate": rate(len(deaths), n),
        "clear_s": [num(r, "frames") / FPS for r in rs if r["outcome"] == "cleared"],
        "time_s": [num(r, "frames") / FPS for r in rs],
        "dmg_per_min": [num(r, "dmg_taken") / max(1e-9, num(r, "frames") / FPS / 60) for r in rs],
        "dealt_ratio": [num(r, "dmg_dealt") / max(1, num(r, "dmg_taken")) for r in rs],
        "timeouts": timeouts,
    }


def status_deaths(rows, window_s):
    """Share of deaths whose last harmful status landed <= window_s before."""
    deaths = [r for r in rows if r["outcome"] == "died"]
    hit = [r for r in deaths if r.get("death_status_kind")
           and 0 <= num(r, "death_status_age") <= window_s * FPS]
    by_kind = defaultdict(int)
    by_stage = defaultdict(lambda: [0, 0])
    for r in deaths:
        by_stage[int(r["stage"])][1] += 1
    for r in hit:
        by_kind[r["death_status_kind"]] += 1
        by_stage[int(r["stage"])][0] += 1
    return len(hit), len(deaths), dict(by_kind), dict(by_stage)


def stage_model(stats, tier, stage, path_rooms):
    """Per-stage pass probability and time (seconds) for one tier."""
    b = boss_summary(stats.get(tier, stage, "boss"))
    rm = room_summary(stats.get(tier, stage, "entry"))
    rooms = path_rooms[stage] * DETOUR_FACTOR
    combat_rooms = rooms * 0.75   # about one cleared room in four is empty
    # Beta posteriors (Jeffreys prior); simulate() draws from them per player
    # so small samples widen the ranges instead of hiding in a point value.
    room_ab = (rm["deaths"] + 0.5, rm["n"] - rm["deaths"] + 0.5) if rm["n"] else (1.0, 32.0)
    boss_ab = (b["wins"] + 0.5, b["n"] - b["wins"] + 0.5) if b["n"] else (1.0, 1.0)
    p_room = 1 - room_ab[0] / sum(room_ab)
    p_boss = boss_ab[0] / sum(boss_ab)
    room_t = q(rm["time_s"], .5) if rm["time_s"] else 40
    from balance_arena import PROFILES
    prof = PROFILES.get(tier)
    think = (sum(prof["think"]) / 2 / FPS) if prof else 0
    boss_t = q(b["ttk_s"], .5) if b["ttk_s"] else (q(b["attempt_s"], .5) if b["attempt_s"] else 120)
    stage_t = (combat_rooms * room_t + rooms * TRANSIT_S + PUZZLES_PER_STAGE * think
               + RIFTWILD_LEG_S[tier] + boss_t)
    death_t = q(b["attempt_s"], .5) if b["attempt_s"] else 60
    return {"p_room": p_room, "rooms": combat_rooms, "p_boss": p_boss,
            "room_ab": room_ab, "boss_ab": boss_ab,
            "p_stage": p_room ** combat_rooms * p_boss, "pre_boss_s": stage_t - boss_t,
            "time_s": stage_t, "boss_attempt_s": death_t, "room_t": room_t}


def simulate(models, tiers_up, rng, learning, cap_h=200):
    """One player's campaign until the first clear; death restarts at stage 1."""
    t = 0.0
    attempts = defaultdict(int)
    furthest_at_2h = 1
    # This player's true odds: one draw from each posterior.
    draw = {s: (1 - rng.betavariate(*models[s]["room_ab"]), rng.betavariate(*models[s]["boss_ab"]))
            for s in models}
    draw_up = ({s: (1 - rng.betavariate(*tiers_up[s]["room_ab"]),
                    rng.betavariate(*tiers_up[s]["boss_ab"])) for s in tiers_up}
               if tiers_up else None)
    while t < cap_h * 3600:
        for stage in range(1, 10):
            m = models[stage]
            p_room, p_boss = draw[stage]
            if learning and draw_up:
                up_room, up_boss = draw_up[stage]
                gain = 1 - (1 - LEARNING_RATE) ** attempts[stage]
                p_boss = p_boss + max(0.0, up_boss - p_boss) * gain
                p_room = p_room + max(0.0, up_room - p_room) * gain
            attempts[stage] += 1
            # Rooms: death part-way through the stage.
            died = False
            for _ in range(max(1, round(m["rooms"]))):
                if rng.random() > p_room:
                    t += m["time_s"] * rng.uniform(0.1, 0.8)
                    died = True
                    break
            if not died:
                if rng.random() > p_boss:
                    t += m["pre_boss_s"] + m["boss_attempt_s"]
                    died = True
            if died:
                if t <= REFUND_WINDOW_MIN * 60:
                    furthest_at_2h = max(furthest_at_2h, stage)
                t += RESTART_OVERHEAD_S
                break
            t += m["time_s"]
            if t <= REFUND_WINDOW_MIN * 60:
                furthest_at_2h = max(furthest_at_2h, stage + 1 if stage < 9 else 9)
        else:
            return t, furthest_at_2h, attempts[1]
    return float("inf"), furthest_at_2h, attempts[1]


def first_clear(stats, path_rooms, tier, learning, trials=2000):
    models = {s: stage_model(stats, tier, s, path_rooms) for s in range(1, 10)}
    order = list(TIERS)
    up_tier = order[order.index(tier) + 1] if order.index(tier) + 1 < len(order) else None
    ups = ({s: stage_model(stats, up_tier, s, path_rooms) for s in range(1, 10)}
           if up_tier else None)
    rng = random.Random(tier + str(learning))
    times, furthest, runs = [], [], []
    for _ in range(trials):
        t, f, n = simulate(models, ups, rng, learning)
        times.append(t)
        furthest.append(f)
        runs.append(n)
    finite = [x for x in times if math.isfinite(x)]
    within_2h = sum(1 for x in times if x <= REFUND_WINDOW_MIN * 60) / trials
    med = q(times, .5) if len(finite) > trials / 2 else float("inf")
    return {
        "p_clear_run": math.prod(m["p_stage"] for m in models.values()),
        "clear_h": [q(times, .25) / 3600, med / 3600, q(times, .75) / 3600],
        "cleared_share": len(finite) / trials,
        "within_2h": within_2h,
        "share_of_clear_in_2h": min(1.0, 2 / (med / 3600)) if math.isfinite(med) and med > 0 else 0.0,
        "furthest_stage_2h": [q(furthest, .25), q(furthest, .5), q(furthest, .75)],
        "runs": [q(runs, .25), q(runs, .5), q(runs, .75)],
        "run_time_min": sum(m["time_s"] for m in models.values()) / 60,
        "models": models,
    }


# Assumed human pass odds per stage (stage 3 separately) for the scenario
# table. The pilot cannot beat Normal Colossi yet, so these bracket what a
# person plausibly does; replace with telemetry when it exists.
SCENARIOS = (("strong", 0.90, 0.70), ("middle", 0.80, 0.45), ("struggling", 0.70, 0.25))


def scenario_clear(models, p_stage, p_stage3, rng, trials):
    """First clear with assumed per-stage pass odds and measured stage times."""
    times, furthest = [], []
    for _ in range(trials):
        t, far = 0.0, 1
        while t < 200 * 3600:
            for stage in range(1, 10):
                p = p_stage3 if stage == 3 else p_stage
                m = models[stage]
                if rng.random() > p:
                    t += m["pre_boss_s"] * rng.uniform(0.3, 1.0) + m["boss_attempt_s"]
                    if t <= REFUND_WINDOW_MIN * 60:
                        far = max(far, stage)
                    t += RESTART_OVERHEAD_S
                    break
                t += m["time_s"]
                if t <= REFUND_WINDOW_MIN * 60:
                    far = max(far, min(9, stage + 1))
            else:
                break
        times.append(t if t < 200 * 3600 else float("inf"))
        furthest.append(far)
    return times, furthest


def spikes(curve, k):
    """Stages whose loss/time metric exceeds k x the mean of their neighbours."""
    out = []
    stages = sorted(curve)
    for i, s in enumerate(stages):
        nb = [curve[stages[j]] for j in (i - 1, i + 1) if 0 <= j < len(stages)]
        nb = [x for x in nb if x is not None and not math.isnan(x)]
        v = curve[s]
        if not nb or v is None or math.isnan(v):
            continue
        base = statistics.mean(nb)
        if v > k * max(base, 0.05):
            out.append((s, v, base))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arena", type=Path, help="CSV from scripts/balance_arena.py")
    ap.add_argument("--runs", type=Path, help="optional stages.csv from balance_sweep.py")
    ap.add_argument("--out", type=Path, default=ROOT / "tmp/balance/report")
    ap.add_argument("--spike-k", type=float, default=2.0)
    ap.add_argument("--status-window", type=float, default=5.0)
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--check", type=Path, help="thresholds JSON; exit 1 on failure")
    args = ap.parse_args()

    rows = load_csv(args.arena)
    stats = Stats(rows)
    tiers = [t for t in TIERS if any(r["skill"] == t for r in rows)]
    stages = sorted({int(r["stage"]) for r in rows})
    path_rooms = {s: critical_path_rooms(s) for s in range(1, 10)}
    md = []
    metrics: dict = {"tiers": tiers, "stages": stages, "slices": len(rows)}
    md.append("# Quintra difficulty report\n")
    md.append(f"{len(rows)} human-model slices; tiers {', '.join(tiers)}; stages "
              f"{stages[0]}-{stages[-1]}. Times in seconds unless noted; "
              "`median (p25-p75)`. Model numbers are **estimates**.\n")

    # --- Stage 3 boss ------------------------------------------------------
    md.append("## Stage 3 Colossus (flagged by playtest)\n")
    md.append("| tier | fights | win rate | deaths | time-to-kill s (wins) | attempt s | dmg taken | max 2 s burst (% max HP) | burst spikes/fight | boss HP left when lost | mean boss HP removed |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    metrics["stage3_boss"] = {}
    for t in tiers:
        b = boss_summary(stats.get(t, 3, "boss"))
        metrics["stage3_boss"][t] = {k: b[k] for k in ("n", "wins", "win_rate", "deaths", "timeouts")}
        metrics["stage3_boss"][t]["ttk_median_s"] = q(b["ttk_s"], .5)
        metrics["stage3_boss"][t]["ttk_s"] = [q(b["ttk_s"], .25), q(b["ttk_s"], .5), q(b["ttk_s"], .75)]
        metrics["stage3_boss"][t]["progress_mean"] = (statistics.mean(b["progress"])
                                                      if b["progress"] else float("nan"))
        metrics["stage3_boss"][t]["burst_frac"] = [q(b["burst_frac"], .25), q(b["burst_frac"], .5),
                                                   q(b["burst_frac"], .75)]
        metrics["stage3_boss"][t]["spikes_per_fight"] = (statistics.mean(b["spikes"])
                                                         if b["spikes"] else float("nan"))
        md.append(f"| {t} | {b['n']} | {fmt(100 * b['win_rate'], 0)}% | {b['deaths']} | "
                  f"{band(b['ttk_s'])} | {band(b['attempt_s'])} | {band(b['dmg'], 0)} | "
                  f"{band(b['burst_frac'], 0, 100)} | {band(b['spikes'], 1)} | "
                  f"{band(b['boss_hp_left'], 0, 100)}% | "
                  f"{fmt(100 * statistics.mean(b['progress']), 0) if b['progress'] else 'n/a'}% |")
    md.append("")

    # --- Status effects ----------------------------------------------------
    md.append("## Status effects at bad moments\n")
    md.append("| tier | harmful landings | per boss-minute | in boss fights | at low HP (≤1/3) | deaths | deaths after status ≤3 s | ≤5 s | ≤10 s | play time within 5 s of a status | lift (≤5 s share / exposure) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    metrics["status"] = {}
    for t in tiers:
        trs = [r for r in rows if r["skill"] == t]
        harm = sum(num(r, "status_harmful") for r in trs)
        inb = sum(num(r, "status_in_boss") for r in trs)
        low = sum(num(r, "status_low_hp") for r in trs)
        boss_min = sum(num(r, "frames") for r in trs if r["kind"] == "boss") / FPS / 60
        shares = []
        for w in STATUS_WINDOWS_S:
            k, n, _, _ = status_deaths(trs, w)
            shares.append((k, n))
        k5, n5, kinds5, st5 = status_deaths(trs, args.status_window)
        frames = sum(num(r, "frames") for r in trs)
        exposed = sum(num(r, "status_exposed_frames") for r in trs
                      if not math.isnan(num(r, "status_exposed_frames")))
        expo = exposed / frames if frames else float("nan")
        lift = rate(k5, n5) / expo if n5 and expo and expo > 0 else float("nan")
        metrics["status"][t] = {"harmful": harm, "in_boss": inb, "low_hp": low,
                                "per_boss_min": inb / boss_min if boss_min else float("nan"),
                                "deaths": n5, "deaths_after_status": k5,
                                "share": rate(k5, n5), "exposure": expo, "lift": lift,
                                "shares_3_5_10": [rate(k, n) for k, n in shares],
                                "by_kind": kinds5,
                                "by_stage": {s: v for s, v in st5.items()}}
        md.append(f"| {t} | {int(harm)} | {fmt(inb / boss_min if boss_min else float('nan'), 2)} | "
                  f"{int(inb)} | {int(low)} | {shares[0][1]} | "
                  + " | ".join(f"{k}/{n} ({fmt(100 * rate(k, n), 0)}%)" for k, n in shares)
                  + f" | {fmt(100 * expo, 0)}% | {fmt(lift, 2)}x |")
    pooled = status_deaths(rows, args.status_window)
    metrics["status_pooled"] = {"deaths": pooled[1], "after_status": pooled[0],
                                "share": rate(pooled[0], pooled[1]), "by_kind": pooled[2]}
    md.append("")
    md.append("Lift compares the share of deaths that follow a status with the share of play "
              "time spent under or just after one: about 1x means statuses are along for the "
              "ride; well above 1x means they cause deaths.\n")
    if pooled[2]:
        md.append(f"Deaths within {args.status_window:g} s of a harmful status, by effect (all tiers): "
                  + ", ".join(f"{k} {v}" for k, v in sorted(pooled[2].items(), key=lambda x: -x[1])))
        md.append("")
        md.append("| stage | deaths | after status ≤5 s |")
        md.append("|---|---|---|")
        for s in sorted(pooled[3]):
            k, n = pooled[3][s]
            md.append(f"| {s} | {n} | {k} ({fmt(100 * rate(k, n), 0)}%) |")
        md.append("")
    kinds_total = defaultdict(int)
    for r in rows:
        for part in filter(None, r.get("status_kinds", "").split(";")):
            name, c = part.split(":")
            kinds_total[name] += int(c)
    if kinds_total:
        md.append("All status landings by type: " + ", ".join(
            f"{k} {v}" for k, v in sorted(kinds_total.items(), key=lambda x: -x[1])))
        md.append("")

    # --- Difficulty curve --------------------------------------------------
    md.append("## Difficulty curve by stage\n")
    md.append("Boss: Colossus fight from its live arena checkpoint. Room: the stage's first combat room at full HP.\n")
    curve_rows = []
    metrics["curve"] = {}
    for t in tiers:
        md.append(f"### {t}\n")
        md.append("| stage | boss win | boss TTK s | boss attempt s | boss dmg | room death | room clear s | room dmg/min | dealt:taken | est. stage min | est. P(pass stage) |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        metrics["curve"][t] = {}
        for s in stages:
            b = boss_summary(stats.get(t, s, "boss"))
            rm = room_summary(stats.get(t, s, "entry"))
            m = stage_model(stats, t, s, path_rooms)
            metrics["curve"][t][s] = {"boss_win": b["win_rate"], "boss_n": b["n"],
                                      "room_death": rm["death_rate"], "room_n": rm["n"],
                                      "stage_min": m["time_s"] / 60, "p_stage": m["p_stage"],
                                      "boss_ttk_s": q(b["ttk_s"], .5),
                                      "boss_progress": (statistics.mean(b["progress"])
                                                        if b["progress"] else float("nan"))}
            md.append(f"| {s} | {b['wins']}/{b['n']} | {band(b['ttk_s'])} | {band(b['attempt_s'])} | "
                      f"{band(b['dmg'], 0)} | {rm['deaths']}/{rm['n']} | {band(rm['time_s'])} | "
                      f"{band(rm['dmg_per_min'])} | {band(rm['dealt_ratio'])} | "
                      f"{fmt(m['time_s'] / 60)} | {fmt(100 * m['p_stage'], 0)}% |")
            curve_rows.append({"tier": t, "stage": s, "boss_n": b["n"], "boss_wins": b["wins"],
                               "boss_ttk_p25": q(b["ttk_s"], .25), "boss_ttk_p50": q(b["ttk_s"], .5),
                               "boss_ttk_p75": q(b["ttk_s"], .75),
                               "boss_dmg_p50": q(b["dmg"], .5), "room_n": rm["n"],
                               "room_deaths": rm["deaths"], "room_time_p25": q(rm["time_s"], .25),
                               "room_time_p50": q(rm["time_s"], .5), "room_time_p75": q(rm["time_s"], .75),
                               "est_stage_min": m["time_s"] / 60, "est_p_stage": m["p_stage"]})
        md.append("")

    # --- Spikes ------------------------------------------------------------
    md.append(f"## Spikes (> {args.spike_k:g}x neighbour mean)\n")
    found = []
    for t in tiers:
        loss = {s: 1 - metrics["curve"][t][s]["boss_win"] for s in stages
                if metrics["curve"][t][s]["boss_n"]}
        rdeath = {s: metrics["curve"][t][s]["room_death"] for s in stages}
        ttk = {s: metrics["curve"][t][s]["boss_ttk_s"] for s in stages}
        for name, cur in (("boss loss rate", loss), ("room death rate", rdeath),
                          ("boss time-to-kill", ttk)):
            for s, v, base in spikes(cur, args.spike_k):
                found.append({"tier": t, "metric": name, "stage": s, "value": v, "neighbours": base})
                md.append(f"- {t}: stage {s} {name} {fmt(v, 2)} vs neighbours {fmt(base, 2)}")
        # When nearly every fight is lost the loss rate is flat; the share of
        # the Colossus's HP removed still shows which fights are walls.
        prog = {s: metrics["curve"][t][s]["boss_progress"] for s in stages}
        inv = {s: (1 / max(v, 0.01) if v is not None and not math.isnan(v) else float("nan"))
               for s, v in prog.items()}
        for s, v, base in spikes(inv, args.spike_k):
            found.append({"tier": t, "metric": "boss HP removed (low)", "stage": s,
                          "value": prog[s], "neighbours": 1 / base})
            md.append(f"- {t}: stage {s} boss HP removed {fmt(100 * prog[s], 0)}% vs neighbours "
                      f"{fmt(100 / base, 0)}%")
    if not found:
        md.append("- none")
    metrics["spikes"] = found
    md.append("")

    # --- First clear -------------------------------------------------------
    md.append("## Estimated human first clear (death wipes the run)\n")
    md.append("| tier | P(clear one run) | clean-run length min | runs to first clear | first-clear hours, no learning | with learning | players clearing within 2 h | 2 h as share of median first-clear time | furthest stage by 2 h |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    metrics["first_clear"] = {}
    for t in tiers:
        a = first_clear(stats, path_rooms, t, learning=False, trials=args.trials)
        b = first_clear(stats, path_rooms, t, learning=True, trials=args.trials)
        metrics["first_clear"][t] = {
            "p_clear_run": a["p_clear_run"], "run_minutes": a["run_time_min"],
            "no_learning_h": a["clear_h"], "learning_h": b["clear_h"],
            "within_2h": b["within_2h"], "share_in_2h": b["share_of_clear_in_2h"],
            "furthest_stage_2h": b["furthest_stage_2h"], "runs": b["runs"]}

        def hrs(x):
            return "/".join(">200" if not math.isfinite(v) else fmt(v) for v in x)
        md.append(f"| {t} | {a['p_clear_run']:.2%} | {fmt(a['run_time_min'], 0)} | "
                  f"{'/'.join(fmt(v, 0) for v in b['runs'])} | {hrs(a['clear_h'])} | {hrs(b['clear_h'])} | "
                  f"{fmt(100 * b['within_2h'], 0)}% | {fmt(100 * b['share_of_clear_in_2h'], 0)}% | "
                  f"{'/'.join(fmt(v, 0) for v in b['furthest_stage_2h'])} |")
    md.append("")
    md.append("Hours are p25/median/p75 over simulated players; each player draws its own odds "
              "from the measured win/death counts, so thin samples widen the range. *Learning* "
              f"moves each stage's pass odds {int(LEARNING_RATE * 100)}% of the way toward the "
              "next tier per visit to that stage. Slices start rooms and the Colossus at the "
              "checkpoint's HP, so attrition between rooms is not modelled: treat the hours as a "
              "lower bound. Stage time = combat rooms x measured room time + transit "
              f"{TRANSIT_S}s/room + puzzles + Riftwild leg + boss; path rooms come from the "
              f"cartridge topology x {DETOUR_FACTOR} detour factor.\n")

    # --- Scenarios ---------------------------------------------------------
    md.append("## First clear under assumed human pass odds (scenario, not measured)\n")
    md.append("Stage lengths are measured per tier above; pass odds are assumptions because the "
              "pilot cannot yet win Normal Colossus fights a person wins.\n")
    md.append("| tier times | scenario | P(pass stage) / stage 3 | P(clear one run) | first-clear hours p25/median/p75 | players clearing within 2 h | 2 h as share of median first clear | furthest stage by 2 h p25/median/p75 |")
    md.append("|---|---|---|---|---|---|---|---|")
    metrics["scenarios"] = {}
    for t in [x for x in ("nonexpert", "average") if x in tiers]:
        models = {s: stage_model(stats, t, s, path_rooms) for s in range(1, 10)}
        for name, ps, p3 in SCENARIOS:
            times, far = scenario_clear(models, ps, p3, random.Random(f"{t}{name}"), args.trials)
            hours = [q(times, x) / 3600 for x in (.25, .5, .75)]
            within = sum(1 for x in times if x <= REFUND_WINDOW_MIN * 60) / len(times)
            share = min(1.0, 2 / hours[1]) if math.isfinite(hours[1]) and hours[1] > 0 else 0.0
            p_run = ps ** 8 * p3
            metrics["scenarios"].setdefault(t, {})[name] = {
                "p_stage": ps, "p_stage3": p3, "p_run": p_run, "hours": hours,
                "within_2h": within, "share_in_2h": share,
                "furthest_2h": [q(far, x) for x in (.25, .5, .75)]}
            md.append(f"| {t} | {name} | {ps:.0%} / {p3:.0%} | {p_run:.1%} | "
                      + "/".join(">200" if not math.isfinite(h) else fmt(h) for h in hours)
                      + f" | {fmt(100 * within, 0)}% | {fmt(100 * share, 0)}% | "
                      + "/".join(fmt(q(far, x), 0) for x in (.25, .5, .75)) + " |")
    md.append("")

    # --- Whole-run harness -------------------------------------------------
    if args.runs and args.runs.exists():
        wr = load_csv(args.runs)
        md.append("## Whole-run mGBA harness health\n")
        md.append("| tier | runs | furthest stage median | died | stalled (pilot lost) | hang | timeout |")
        md.append("|---|---|---|---|---|---|---|")
        by = defaultdict(list)
        for r in wr:
            by[r["skill"]].append(r)
        health = {}
        for t, rs in by.items():
            runs = defaultdict(list)
            for r in rs:
                runs[(r["run"], r["class"])].append(r)
            last = [max(v, key=lambda r: int(r["stage"])) for v in runs.values()]
            oc = defaultdict(int)
            for r in last:
                oc[r["outcome"]] += 1
            health[t] = dict(oc)
            md.append(f"| {t} | {len(last)} | {q([int(r['stage']) for r in last], .5):.0f} | "
                      f"{oc['died']} | {oc['stalled']} | {oc['hang']} | {oc['timeout']} |")
        metrics["whole_run"] = health
        md.append("")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text("\n".join(md) + "\n")
    if curve_rows:
        with (args.out / "curve.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(curve_rows[0]))
            w.writeheader()
            w.writerows(curve_rows)
    (args.out / "metrics.json").write_text(json.dumps(clean(metrics), indent=2, default=str))
    print(f"[report] {args.out / 'report.md'}")

    if args.check:
        th = json.loads(args.check.read_text())
        fails = []
        s3 = metrics["stage3_boss"].get(th.get("stage3_tier", "average"))
        if s3 is not None and s3["n"]:
            lo, hi = th.get("stage3_boss_win_rate_min"), th.get("stage3_boss_win_rate_max")
            if lo is not None and s3["win_rate"] < lo:
                fails.append(f"stage 3 boss win rate {s3['win_rate']:.2f} < {lo}")
            if hi is not None and s3["win_rate"] > hi:
                fails.append(f"stage 3 boss win rate {s3['win_rate']:.2f} > {hi}")
            pmin = th.get("stage3_boss_progress_min")
            if pmin is not None and not math.isnan(s3["progress_mean"]) and s3["progress_mean"] < pmin:
                fails.append(f"stage 3 boss HP removed {s3['progress_mean']:.2f} < {pmin}")
        sd = metrics["status_pooled"]
        smax = th.get("status_death_share_max")
        if smax is not None and sd["deaths"] >= th.get("status_min_deaths", 4) and sd["share"] > smax:
            fails.append(f"deaths after status {sd['share']:.2f} > {smax}")
        kmax = th.get("max_boss_loss_spike_ratio")
        if kmax is not None:
            for sp in found:
                if sp["metric"] == "boss loss rate" and sp["tier"] == th.get("stage3_tier", "average") \
                        and sp["value"] > kmax * max(sp["neighbours"], 0.05):
                    fails.append(f"{sp['tier']} stage {sp['stage']} boss loss spike {sp['value']:.2f}")
        print("[report] gate: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
