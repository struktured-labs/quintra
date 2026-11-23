#!/usr/bin/env python3
"""Room-level status-effect report for Quintra (non-boss combat rooms).

Reads the fight + event CSVs written by ``scripts/balance_rooms.py fight``
(one pair per difficulty) and writes a markdown report and a metrics JSON:

  * outcomes per stage and tier (cleared / died / timeout, finished fights);
  * status landings per hit taken, overall and per status, and the carrier
    proc rate (hits from an enemy whose attack carries status X that land X);
  * HP at the moment each status landed (hearts; 1 HP = half a heart);
  * share of deaths within 5 s / 10 s of a harmful status landing versus the
    share of fight time spent inside such a window (timing-only baseline),
    and their ratio (lift), overall, per stage and per status;
  * chained patterns at death: Stop then a hit, Confusion near hazards,
    Blind in a crowd, DoT pinning HP at half a heart then a hit, and a new
    status replacing an old one; plus how often each pattern occurs at all;
  * the Ember Depths Cinder subset (rooms with Cinder Maw / Cinder Kite).

Everything is recomputed from the event log, so the windows and status set
are defined here, not in the harness.  ``--check thresholds.json`` exits 1
when a room gate fails.

Usage:
  python3 scripts/balance_rooms_report.py tmp/balance/rooms-normal.csv \
      tmp/balance/rooms-easy.csv --out tmp/balance/rooms-report
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 59.7275
TIERS = ("nonexpert", "average", "skilled", "bot")
# Every hostile status the player slot can hold (inversion is index 13).
STATUSES = ("burn", "poison", "bleed", "slow", "stop", "confusion", "blind",
            "mute", "brittle", "curse", "inversion")

DOT_KINDS = {"poison", "burn", "bleed"}
STATUS_INVOLVED_WINDOW = 600  # 10 s lift window; DoT floor means Burn cannot kill directly
WINDOWS = (5, 10)
STOP_HIT_FRAMES = 14 * 8          # Stop lasts 14 ticks x 8 frames
CROWD = 3


def load(path: Path):
    rows = list(csv.DictReader(path.open()))
    ev_path = path.with_suffix(".events.csv")
    events = list(csv.DictReader(ev_path.open())) if ev_path.exists() else []
    return rows, events


def key(r):
    return (r["skill"], r["seed"], r["hero"], r["stage"], r["difficulty"], r["fixture"])


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(x, nd=0):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{nd}f}%"


def num(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def quant(v, p):
    if not v:
        return float("nan")
    v = sorted(v)
    k = (len(v) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def clean(x):
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


class Fight:
    """One fight with its events, plus the derived per-fight measures."""

    def __init__(self, row, events):
        self.row = row
        self.stage = int(row["stage"])
        self.skill = row["skill"]
        self.outcome = row["outcome"]
        self.frames = int(row["frames"])
        self.cinder = row.get("cinder") == "1"
        self.lands = [e for e in events if e["event"] == "status" and e["kind"] in STATUSES]
        self.hits = [e for e in events if e["event"] == "hit"]
        deaths = [e for e in events if e["event"] == "death"]
        self.death = int(deaths[0]["frame"]) if deaths else (self.frames if self.outcome == "died" else None)
        self.death_ev = deaths[0] if deaths else None
        land_f = [int(e["frame"]) for e in self.lands]
        # Hits that landed no status: the hit-matched control for the lift.
        self.plain = [int(h["frame"]) for h in self.hits
                      if h["procced"] != "1" and not any(abs(int(h["frame"]) - t) <= 3 for t in land_f)]
        self.chain = set(filter(None, row.get("death_chain", "").split("+")))

    def starts(self, kind=None):
        if kind == "plain_hit":
            return self.plain
        return [int(e["frame"]) for e in self.lands if not kind or e["kind"] == kind]

    def cover(self, window_f, kind=None):
        cov = set()
        for f0 in self.starts(kind):
            cov.update(range(f0, min(self.frames, f0 + window_f)))
        return len(cov)

    def death_age(self, kind=None):
        """Frames from the last landing (of ``kind``) to the death.

        A status that procs on the killing blow itself (within 3 frames of
        death) did not cause that death, so it is not counted.
        """
        if self.death is None:
            return None
        prior = [t for t in self.starts(kind) if t < self.death - 3]
        return self.death - max(prior) if prior else None

    def last_kind(self):
        if self.death is None:
            return None
        prior = [e for e in self.lands if int(e["frame"]) < self.death - 3]
        return prior[-1]["kind"] if prior else None

    def status_involved(self):
        """Poison/Burn/Bleed was active at the killing blow, a landing of
        those was within the 10 s (600-frame) lift window, or a direct
        Poison/Bleed tick took the last HP (dot_kill). Burn itself cannot
        kill; a nearby Burn still counts because the DoT floor left the
        champion at 1 HP for the finishing hit.
        """
        if self.outcome != "died":
            return False
        if "dot_kill" in self.chain:
            return True
        if self.death_ev and (self.death_ev.get("status_active") or "") in DOT_KINDS:
            return True
        if self.death is None:
            return False
        for e in self.lands:
            if e.get("kind") in DOT_KINDS:
                try:
                    age = self.death - int(e["frame"])
                except (TypeError, ValueError):
                    continue
                if 0 <= age <= STATUS_INVOLVED_WINDOW:
                    return True
        return False


def lift_block(fights, window_s, kind=None):
    wf = int(window_s * FPS)
    deaths = [f for f in fights if f.outcome == "died"]
    near = 0
    for f in deaths:
        if kind in (None, "plain_hit"):
            age = f.death_age(kind)
        else:
            age = f.death_age() if f.last_kind() == kind else None
        if age is not None and age < wf:
            near += 1
    total = sum(f.frames for f in fights)
    exposed = sum(f.cover(wf, kind) for f in fights)
    share = near / len(deaths) if deaths else float("nan")
    base = exposed / total if total else float("nan")
    lo, hi = wilson(near, len(deaths))
    lift = share / base if deaths and base else float("nan")
    return dict(deaths=len(deaths), near=near, share=share, share_lo=lo, share_hi=hi,
                exposure=base, lift=lift,
                lift_lo=(lo / base if base else float("nan")),
                lift_hi=(hi / base if base else float("nan")))


def status_block(fights):
    out = {}
    hits_all = sum(len(f.hits) for f in fights)
    for k in STATUSES:
        carrier = [h for f in fights for h in f.hits if h["carrier"] == k]
        procced = sum(1 for h in carrier if h["procced"] == "1")
        lands = [e for f in fights for e in f.lands if e["kind"] == k]
        hp = [int(e["hp"]) / 2 for e in lands]
        low = sum(1 for e in lands if int(e["hp"]) <= 2)
        out[k] = dict(carrier_hits=len(carrier), procced=procced,
                      proc=(procced / len(carrier) if carrier else float("nan")),
                      lands=len(lands), per_hit=(len(lands) / hits_all if hits_all else float("nan")),
                      hp_med=quant(hp, .5), hp_p25=quant(hp, .25), hp_p75=quant(hp, .75),
                      low_share=(low / len(lands) if lands else float("nan")),
                      replaced=sum(1 for e in lands if e["replaced"]),
                      lift10=lift_block(fights, 10, k))
    return out


def chain_block(fights):
    deaths = [f for f in fights if f.outcome == "died"]
    labels = ("stop_then_hit", "confusion_near_hazard", "blind_in_crowd",
              "dot_pinned_then_hit", "status_replaced")
    at_death = {lab: sum(1 for f in deaths if lab in f.chain) for lab in labels}
    # How common is each setup at all (per landing), death or not?
    stops = [(f, int(e["frame"])) for f in fights for e in f.lands if e["kind"] == "stop"]
    stop_hit = sum(1 for f, t in stops if any(0 < int(h["frame"]) - t <= STOP_HIT_FRAMES for h in f.hits))
    conf = [e for f in fights for e in f.lands if e["kind"] == "confusion"]
    blind = [e for f in fights for e in f.lands if e["kind"] == "blind"]
    burns = [(f, e) for f in fights for e in f.lands if e["kind"] == "burn"]
    lands = [e for f in fights for e in f.lands]
    return dict(deaths=len(deaths), at_death=at_death,
                stop_lands=len(stops), stop_hit=stop_hit,
                confusion_lands=len(conf), confusion_hazard=sum(1 for e in conf if e["hazard_near"] == "1"),
                blind_lands=len(blind), blind_crowd=sum(1 for e in blind if int(e["crowd"] or 0) >= CROWD),
                burn_lands=len(burns), lands=len(lands),
                replaced=sum(1 for e in lands if e["replaced"]),
                pinned_fights=sum(1 for f in fights if f.row.get("death_chain", "").find("dot_pinned") >= 0))


def outcome_block(fights):
    n = len(fights)
    c = defaultdict(int)
    for f in fights:
        c[f.outcome] += 1
    fin = c["died"] + c["cleared"]
    hits = sum(len(f.hits) for f in fights)
    lands = sum(len(f.lands) for f in fights)
    involved = [f for f in fights if f.status_involved()]
    burn_inv = [f for f in involved if (
        (f.death_ev and f.death_ev.get("status_active") == "burn")
        or any(e.get("kind") == "burn" for e in f.lands))]
    return dict(fights=n, cleared=c["cleared"], died=c["died"], timeout=c["timeout"],
                left=c["left_room"], finished=fin,
                death_rate=(c["died"] / fin if fin else float("nan")),
                death_rate_of_fights=(c["died"] / n if n else float("nan")),
                status_involved=len(involved),
                status_involved_share=(len(involved) / c["died"] if c["died"] else float("nan")),
                status_involved_rate=(len(involved) / n if n else float("nan")),
                burn_involved=len(burn_inv),
                unfinished=((n - fin) / n if n else float("nan")),
                hits=hits, lands=lands, lands_per_hit=(lands / hits if hits else float("nan")),
                hit_rate_min=(hits / (sum(f.frames for f in fights) / FPS / 60) if fights else float("nan")))


def summarize(fights):
    l5, l10 = lift_block(fights, 5), lift_block(fights, 10)
    c5, c10 = lift_block(fights, 5, "plain_hit"), lift_block(fights, 10, "plain_hit")
    for l, c in ((l5, c5), (l10, c10)):
        l["control_lift"] = c["lift"]
        l["control_share"] = c["share"]
        l["excess"] = l["lift"] / c["lift"] if c["lift"] and math.isfinite(c["lift"]) else float("nan")
    return dict(outcome=outcome_block(fights), lift5=l5, lift10=l10,
                status=status_block(fights), chains=chain_block(fights))


def build(rows, events):
    by = defaultdict(list)
    for e in events:
        by[key(e)].append(e)
    fights = [Fight(r, by.get(key(r), [])) for r in rows]
    out = {"all": summarize(fights), "stage": {}, "stage_tier": {}, "tier": {}}
    for s in sorted({f.stage for f in fights}):
        fs = [f for f in fights if f.stage == s]
        out["stage"][s] = summarize(fs)
        for t in TIERS:
            ft = [f for f in fs if f.skill == t]
            if ft:
                out["stage_tier"][f"{s}:{t}"] = summarize(ft)
    for t in TIERS:
        ft = [f for f in fights if f.skill == t]
        if ft:
            out["tier"][t] = summarize(ft)
    early = [f for f in fights if f.stage <= 3]
    out["stages_1_3"] = summarize(early)
    for t in TIERS:
        ft = [f for f in early if f.skill == t]
        if ft:
            out.setdefault("stages_1_3_tier", {})[t] = summarize(ft)
    s3 = [f for f in fights if f.stage == 3]
    out["cinder"] = summarize([f for f in s3 if f.cinder])
    out["ember_other"] = summarize([f for f in s3 if not f.cinder])
    return out


def md_difficulty(name, m):
    L = [f"## {name.title()} (measured)", ""]
    a = m["all"]["outcome"]
    L += [f"{a['fights']} room fights; {a['finished']} finished "
          f"({pct(1 - a['unfinished'])}), {a['died']} deaths, {a['timeout']} timeouts, "
          f"{a['left']} left the room. Status-involved deaths (Poison/Burn/Bleed "
          f"active or within the 10 s lift window, or a direct Poison/Bleed tick "
          f"kill): {a.get('status_involved', 0)}/{a['died']} deaths "
          f"({pct(a.get('status_involved_share'))}); "
          f"{pct(a.get('status_involved_rate'))} of all fights.", ""]
    L += ["### Outcomes and status-death lift per stage and tier (measured)", "",
          "| Stage | Tier | Fights | Finished | Death rate | Hits/min | Status lands per hit | "
          "Deaths ≤5 s after status | Time in 5 s window | Lift 5 s | Deaths ≤10 s | Time in 10 s window | Lift 10 s | "
          "Control lift 10 s (plain hits) | Status/control |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in sorted(m["stage"], key=int):
        for t in TIERS:
            b = m["stage_tier"].get(f"{s}:{t}")
            if not b:
                continue
            o, l5, l10 = b["outcome"], b["lift5"], b["lift10"]
            L.append(f"| {s} | {t} | {o['fights']} | {o['finished']} | {pct(o['death_rate'])} | "
                     f"{num(o['hit_rate_min'], 1)} | {num(o['lands_per_hit'])} | "
                     f"{l5['near']}/{l5['deaths']} ({pct(l5['share'])}) | {pct(l5['exposure'])} | {num(l5['lift'])} | "
                     f"{l10['near']}/{l10['deaths']} ({pct(l10['share'])}) | {pct(l10['exposure'])} | {num(l10['lift'])} | {num(l10['control_lift'])} | {num(l10['excess'])} |")
        b = m["stage"][s]
        o, l5, l10 = b["outcome"], b["lift5"], b["lift10"]
        L.append(f"| **{s}** | **all** | {o['fights']} | {o['finished']} | {pct(o['death_rate'])} | "
                 f"{num(o['hit_rate_min'], 1)} | {num(o['lands_per_hit'])} | "
                 f"{l5['near']}/{l5['deaths']} ({pct(l5['share'])}) | {pct(l5['exposure'])} | **{num(l5['lift'])}** | "
                 f"{l10['near']}/{l10['deaths']} ({pct(l10['share'])}) | {pct(l10['exposure'])} | **{num(l10['lift'])}** | {num(l10['control_lift'])} | **{num(l10['excess'])}** |")
    L.append("")
    for label, blk in (("all stages", m["all"]), ("stages 1-3", m["stages_1_3"]),
                       ("Ember Depths Cinder rooms (Cinder Maw/Kite)", m["cinder"]),
                       ("Ember Depths other rooms", m["ember_other"])):
        L += [f"### Per status, {label} (measured)", "",
              "| Status | Carrier hits | Proc per carrier hit | Lands | Lands per hit taken | "
              "HP at landing, hearts (p25-p75) | Landed at ≤1 heart | Replaced an active status | "
              "Deaths ≤10 s after it | Time in its 10 s window | Lift 10 s |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k in STATUSES:
            s = blk["status"][k]
            if not (s["carrier_hits"] or s["lands"]):
                continue
            if k == "curse" and not s["lands"]:
                k = "curse (Gloam Leech uses the separate curse system; no slot landings)"
            lb = s["lift10"]
            L.append(f"| {k} | {s['carrier_hits']} | {pct(s['proc'])} | {s['lands']} | {num(s['per_hit'], 3)} | "
                     f"{num(s['hp_med'], 1)} ({num(s['hp_p25'], 1)}-{num(s['hp_p75'], 1)}) | {pct(s['low_share'])} | "
                     f"{s['replaced']} | {lb['near']}/{lb['deaths']} | {pct(lb['exposure'], 1)} | {num(lb['lift'])} |")
        o, l10 = blk["outcome"], blk["lift10"]
        L += ["", f"Overall: {o['fights']} fights, {o['finished']} finished, death rate "
              f"{pct(o['death_rate'])}; {o['lands']} landings over {o['hits']} hits taken "
              f"({num(o['lands_per_hit'])} per hit); deaths within 10 s of a status "
              f"{l10['near']}/{l10['deaths']} ({pct(l10['share'])}, 95% CI {pct(l10['share_lo'])}-{pct(l10['share_hi'])}) "
              f"vs {pct(l10['exposure'])} of fight time, lift {num(l10['lift'])} "
              f"(CI {num(l10['lift_lo'])}-{num(l10['lift_hi'])}); the same measure after hits that landed "
              f"no status gives {num(l10['control_lift'])}, so status windows are "
              f"{num(l10['excess'])}x as deadly as plain-hit windows.", ""]
    L += ["### Chained effects (measured)", "",
          "| Scope | Deaths | Stop→hit at death | Confusion near spikes at death | Blind in crowd (≥3 within 48 px) at death | "
          "DoT pinned at ½ heart→hit at death | Status replaced (10 s before death) | Stop lands followed by a hit during Stop | "
          "Confusion lands near spikes | Blind lands in a crowd | Landings that replaced another status |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for label, blk in [("all", m["all"]), ("stages 1-3", m["stages_1_3"]), ("Cinder rooms", m["cinder"])] + \
            [(f"stage {s}", m["stage"][s]) for s in sorted(m["stage"], key=int)]:
        c = blk["chains"]
        ad = c["at_death"]
        L.append(f"| {label} | {c['deaths']} | {ad['stop_then_hit']} | {ad['confusion_near_hazard']} | "
                 f"{ad['blind_in_crowd']} | {ad['dot_pinned_then_hit']} | {ad['status_replaced']} | "
                 f"{c['stop_hit']}/{c['stop_lands']} | {c['confusion_hazard']}/{c['confusion_lands']} | "
                 f"{c['blind_crowd']}/{c['blind_lands']} | {c['replaced']}/{c['lands']} |")
    L.append("")
    return L



def estimate_status_involved_per_run(metrics, th):
    """Estimated status-involved deaths per average Normal run.

    The whole-run bot (#203) cannot finish a Normal run, so this uses
    per-stage combat-room rates times the mean shortest-path room count
    (entry to boss, excluding the boss room) from quintra_topology.
    Stage 3 is split into Maw/Kite vs other rooms with a documented
    natural Maw/Kite share, because the CI fixture set oversamples them.
    Stages missing from the CSV use frozen rates in the thresholds file.
    Treating every path room as a combat court may overestimate slightly;
    a result under 1 is therefore a real miss of the floor.
    """
    est = th.get("run_estimate") or {}
    path = {int(k): float(v) for k, v in (est.get("path_rooms_excluding_boss") or {}).items()}
    share = float(est.get("ember_cinder_natural_share", 0.10))
    frozen = {}
    for k, v in (est.get("frozen_stage_status_involved_rate") or {}).items():
        try:
            frozen[int(k)] = float(v)
        except (TypeError, ValueError):
            continue
    m = metrics.get("normal") or {}
    parts = {}
    total = 0.0

    def _rate(blk):
        if not blk:
            return None
        r = (blk.get("outcome") or {}).get("status_involved_rate")
        return r if r is not None and r == r else None

    def _first_rate(*blks):
        for blk in blks:
            r = _rate(blk)
            if r is not None:
                return r
        return None

    def _stage_rate(stage):
        # Prefer the average skill tier when the CSV mixed tiers.
        # Do not use `or` on the rate: a measured 0.0 is a real rate.
        return _first_rate(
            (m.get("stage_tier") or {}).get(f"{stage}:average"),
            (m.get("stage") or {}).get(stage),
            (m.get("stage") or {}).get(str(stage)),
        )

    for stage, nrooms in path.items():
        rate = None
        if stage == 3:
            p_c = _rate(m.get("cinder"))
            p_o = _rate(m.get("ember_other"))
            if p_c is not None and p_o is not None:
                # CI and local sweeps oversample Maw/Kite; mix back to the
                # natural combat-court share (~10%) so the per-run estimate
                # is not inflated by the fixture boost.
                rate = share * p_c + (1.0 - share) * p_o
            elif p_c is not None and p_o is None:
                # Only Cinder rooms in the CSV (unit tests / cinder-only).
                # Do not scale by natural share; fall through to frozen
                # other-room contribution via missing-stage handling? No:
                # use the measured Cinder rate only for the Cinder share
                # and frozen or None for the rest of Ember.
                other = frozen.get(3)  # frozen is whole-stage; last resort
                if other is not None:
                    rate = share * p_c + (1.0 - share) * other
                else:
                    rate = p_c
        if rate is None:
            rate = _stage_rate(stage)
        if rate is None:
            rate = frozen.get(stage)
        if rate is None:
            continue
        contrib = nrooms * rate
        parts[str(stage)] = {"path_rooms": nrooms, "rate": rate, "contrib": contrib}
        total += contrib
    return {"per_run": total, "parts": parts, "method": (
        "critical_path_rooms (entry-to-boss maze distance, boss excluded) "
        "times combat-room status-involved death rate (Poison/Burn/Bleed "
        "active at the killing blow, a landing within the 10 s / 600-frame "
        "lift window, or a direct Poison/Bleed tick kill). Stage 3 mixes "
        "Maw/Kite vs other rooms at the natural ~10% Cinder share so the "
        "harness oversample does not inflate the estimate. Stages missing "
        "from the CSV use frozen_stage_status_involved_rate.")}



def md_run_estimate(est):
    L = ["## Status-involved deaths per average Normal run (estimated)", "",
         est["method"] + " The whole-run bot cannot finish a Normal run (#203), "
         "so this is a path-length estimate, not a measured full-run death count. "
         "Treating every path room as a combat court may overestimate slightly.", "",
         "| Stage | Path rooms (excl. boss) | Status-involved rate | Contribution |",
         "|---|---|---|---|"]
    for stage in sorted(est["parts"], key=int):
        p = est["parts"][stage]
        L.append(f"| {stage} | {num(p['path_rooms'], 2)} | {pct(p['rate'])} | {num(p['contrib'], 2)} |")
    L += ["", f"**Estimated status-involved deaths per average Normal run: "
          f"{num(est['per_run'], 2)}.** The Normal-mode floor is at least 1.", ""]
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fights", nargs="+", type=Path, help="rooms-<difficulty>.csv files")
    ap.add_argument("--out", type=Path, default=ROOT / "tmp/balance/rooms-report")
    ap.add_argument("--check", type=Path, help="thresholds JSON (rooms section); exit 1 on failure")
    args = ap.parse_args()
    metrics = {}
    for path in args.fights:
        rows, events = load(path)
        if not rows:
            continue
        diff = rows[0]["difficulty"]
        metrics[diff] = build(rows, events)
    args.out.mkdir(parents=True, exist_ok=True)
    L = ["# Quintra room status report", "",
         "Non-boss combat rooms, spawned from per-room fixtures (real enemy set, "
         "progression-matched HP/gear). All numbers below are measured from "
         "headless fights; tiers are modelled human skill levels.", ""]
    for diff in ("normal", "easy"):
        if diff in metrics:
            L += md_difficulty(diff, metrics[diff])
    if {"normal", "easy"} <= metrics.keys():
        L += ["## Normal vs Easy (measured)", "",
              "| Scope | Difficulty | Death rate | Status lands per hit | Lift 5 s | Lift 10 s | "
              "Control lift 10 s | Status/control 10 s |",
              "|---|---|---|---|---|---|---|---|"]
        for label, sel in (("all", lambda m: m["all"]), ("stages 1-3", lambda m: m["stages_1_3"]),
                           ("Cinder rooms", lambda m: m["cinder"])):
            for d in ("normal", "easy"):
                b = sel(metrics[d])
                L.append(f"| {label} | {d} | {pct(b['outcome']['death_rate'])} | "
                         f"{num(b['outcome']['lands_per_hit'])} | {num(b['lift5']['lift'])} | {num(b['lift10']['lift'])} | "
                         f"{num(b['lift10']['control_lift'])} | {num(b['lift10']['excess'])} |")
        L.append("")
    th_all = {}
    if args.check and args.check.exists():
        th_all = json.loads(args.check.read_text())
    th_rooms = th_all.get("rooms", {})
    if "normal" in metrics and th_rooms.get("run_estimate"):
        metrics["normal"]["_run_estimate"] = estimate_status_involved_per_run(metrics, th_rooms)
        L += md_run_estimate(metrics["normal"]["_run_estimate"])
    (args.out / "rooms-report.md").write_text("\n".join(L))
    (args.out / "rooms-metrics.json").write_text(json.dumps(clean(metrics), indent=1))
    print(f"[rooms-report] wrote {args.out / 'rooms-report.md'}")
    if not args.check:
        return 0
    th = th_rooms
    fails = []
    for diff, m in metrics.items():
        scope = m["stages_1_3_tier"].get(th.get("tier", "average")) if "stages_1_3_tier" in m else None
        if not scope:
            continue
        l10 = scope["lift10"]
        if l10["deaths"] >= th.get("min_deaths", 8) and l10["lift"] > th.get(f"lift10_max_{diff}", float("inf")):
            fails.append(f"{diff}: stage 1-3 {th.get('tier', 'average')} room status lift10 "
                         f"{l10['lift']:.2f} > {th[f'lift10_max_{diff}']}")
        lph = scope["outcome"]["lands_per_hit"]
        cap = th.get(f"lands_per_hit_max_{diff}")
        if cap is not None and scope["outcome"]["hits"] >= th.get("min_hits", 30) and lph > cap:
            fails.append(f"{diff}: stage 1-3 status lands per hit {lph:.2f} > {cap}")
    # Trim gates (Normal only): Maw/Kite death rate stays below the cap,
    # and the estimated status-involved deaths per average run stay >= 1.
    if "normal" in metrics:
        nm = metrics["normal"]
        cinder = nm.get("cinder") or {}
        cout = cinder.get("outcome") or {}
        cap = th.get("cinder_death_rate_max_normal")
        min_c = th.get("cinder_min_finished", 8)
        if cap is not None and cout.get("finished", 0) >= min_c:
            rate = cout.get("death_rate")
            if rate == rate and rate > cap:
                fails.append(f"normal: Maw/Kite room death rate {rate:.2f} > {cap}")
        if th.get("status_involved_per_run_min_normal") is not None:
            est = estimate_status_involved_per_run(metrics, th)
            floor = th["status_involved_per_run_min_normal"]
            if est["per_run"] < floor:
                fails.append(
                    f"normal: estimated status-involved deaths per average run "
                    f"{est['per_run']:.2f} < {floor}")
            # Stash for the report markdown.
            metrics["normal"]["_run_estimate"] = est
    for f in fails:
        print(f"[rooms-check] FAIL {f}")
    if not fails:
        print("[rooms-check] ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
