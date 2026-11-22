#!/usr/bin/env python3
"""Human-skill boss and room slices on progression-matched PyBoy checkpoints.

For every (skill tier, hero, stage, seed) this loads a `make stage-states`
checkpoint and lets the maintained PyBoy pilot (run_pyboy_checkpoints.
controller_action) play through a human filter:

  * reaction delay: a new hostile shot is invisible to the pilot until it has
    been on screen for `reaction` frames,
  * imperfect dodging: a share of shots is never noticed at all,
  * lapses (stale input), D-pad slips, aim error on attack presses and
    dropped attack inputs, plus an orientation pause on arrival.

The same tiers and numbers drive the mGBA whole-run model in
scripts/quintra_human_model.lua (test_balance_harness.py keeps them equal).

Checkpoint kinds:
  boss  live Colossus arena; ends on the kill, death, or --boss-frames.
  entry first room of the stage; ends when its hostiles are gone (room
        clear), on death, or --room-frames.

Output: one CSV row per slice in --out (default tmp/balance/arena.csv) with
time, damage taken vs dealt, burst damage, HP, status-effect landings (all,
during a boss, at low HP) and the status that preceded a death.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
# Keep in step with QH_PROFILES in scripts/quintra_human_model.lua.
PROFILES = {
    "skilled": dict(reaction=15, miss=0.10, lapse=0.0015, lapse_len=(6, 12),
                    slip=0.04, slip_len=(2, 5), aim=0.06, drop=0.03, drop_len=(3, 6),
                    think=(180, 600), pause=(6, 18)),
    "average": dict(reaction=21, miss=0.25, lapse=0.0035, lapse_len=(10, 20),
                    slip=0.10, slip_len=(3, 8), aim=0.14, drop=0.08, drop_len=(4, 10),
                    think=(600, 1800), pause=(18, 45)),
    "nonexpert": dict(reaction=27, miss=0.40, lapse=0.0060, lapse_len=(15, 30),
                      slip=0.20, slip_len=(4, 12), aim=0.22, drop=0.15, drop_len=(6, 14),
                      think=(1200, 4500), pause=(30, 90)),
}
SKILLS = ("bot",) + tuple(PROFILES)
STATUS_NAMES = ("", "poison", "burn", "slow", "stop", "blind", "confusion", "mute",
                "brittle", "bleed", "curse", "regen", "haste", "inversion")
HARMFUL = set(range(1, 11))
BURST_WINDOW = 120
BURST_SPIKE_FRACTION = 0.4
LOW_HP_FRACTION = 1 / 3
FIELDS = ("skill,seed,hero,class,stage,kind,difficulty,outcome,frames,dmg_taken,"
          "dmg_dealt,hits,hp_start,hp_end,hp_min,hp_max,boss_hp_start,boss_hp_end,"
          "burst_max_2s,burst_spikes,status_lands,status_harmful,status_in_boss,"
          "status_low_hp,status_kinds,death_status_kind,death_status_age,"
          "death_status_active,death_burst_2s,missed_dodges,lapses,"
          "status_exposed_frames").split(",")
# Exposure window after a harmful status lands (frames), for death lift.
STATUS_WINDOW = 300

# PyBoy env action bits.
A_UP, A_RIGHT, A_DOWN, A_LEFT, A_A, A_B = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
DIRMASK = A_UP | A_RIGHT | A_DOWN | A_LEFT
DIRS = (A_RIGHT, A_RIGHT | A_DOWN, A_DOWN, A_DOWN | A_LEFT,
        A_LEFT, A_LEFT | A_UP, A_UP, A_UP | A_RIGHT)


class HumanFilter:
    """Degrade one pilot's per-frame decision like a person's hands."""

    def __init__(self, skill: str, seed: int, cls: int = 0):
        self.p = PROFILES.get(skill)
        self.rng = random.Random(f"{skill}:{seed}:{cls}")
        self.proj: dict[int, tuple[int, bool]] = {}
        self.lapse = self.slip = self.aim = self.drop = 0
        self.lapse_keys = self.slip_dir = self.aim_dir = self.last = self.last_in = 0
        self.think = self.between(self.p["pause"]) if self.p else 0
        self.missed = self.lapses = 0

    def between(self, rng: tuple[int, int]) -> int:
        return self.rng.randint(rng[0], rng[1])

    def scan(self, mem, entities: int, frame: int) -> set[tuple[int, int]]:
        """Track shot slots; return positions of shots the human cannot see yet."""
        hidden = set()
        live = set()
        for slot in range(32):
            base = entities + slot * 28
            flags = mem[base + 1]
            if mem[base] == 1 and (flags & 1) and not (flags & 0x10):
                live.add(slot)
                if slot not in self.proj:
                    missed = bool(self.p) and self.rng.random() < self.p["miss"]
                    self.missed += missed
                    self.proj[slot] = (frame, missed)
                born, missed = self.proj[slot]
                if self.p and (missed or frame - born < self.p["reaction"]):
                    x = mem[base + 3] | (mem[base + 4] << 8)
                    y = mem[base + 7] | (mem[base + 8] << 8)
                    hidden.add((x - 0x10000 if x & 0x8000 else x,
                                y - 0x10000 if y & 0x8000 else y))
        for slot in list(self.proj):
            if slot not in live:
                del self.proj[slot]
        return hidden

    def apply(self, keys: int, threatened: bool) -> int:
        p = self.p
        if not p:
            return keys
        if self.think > 0:
            self.think -= 1
            if not threatened:
                self.last = 0
                return 0
            self.think = 0
        out = keys
        if self.lapse > 0:
            self.lapse -= 1
            out = self.lapse_keys
        elif self.rng.random() < p["lapse"]:
            self.lapse, self.lapse_keys = self.between(p["lapse_len"]), self.last
            self.lapses += 1
            out = self.lapse_keys
        a_edge = bool(out & A_A) and not (self.last & A_A)
        if a_edge:
            self.aim = 0
            d = out & DIRMASK
            if d in DIRS and self.rng.random() < p["aim"]:
                i = DIRS.index(d)
                self.aim, self.aim_dir = 10, DIRS[(i + self.rng.choice((-1, 1))) % 8]
        if self.aim > 0 and (out & A_A) and (out & DIRMASK):
            self.aim -= 1
            out = (out & ~DIRMASK) | self.aim_dir
        elif not out & A_A:
            self.aim = 0
        if self.slip > 0:
            self.slip -= 1
            out = (out & ~DIRMASK) | self.slip_dir
        elif ((out & DIRMASK) and (keys & DIRMASK) != (self.last_in & DIRMASK)
              and self.rng.random() < p["slip"]):
            # Slips happen when the hand changes direction, not mid-hold.
            self.slip = self.between(p["slip_len"]) - 1
            self.slip_dir = 0 if self.rng.random() < 0.3 else self.rng.choice(DIRS)
            out = (out & ~DIRMASK) | self.slip_dir
        if self.drop > 0:
            self.drop -= 1
            out &= ~A_A
        elif a_edge and self.rng.random() < p["drop"]:
            self.drop = self.between(p["drop_len"]) - 1
            out &= ~A_A
        self.last_in = keys
        self.last = out
        return out


def noi_symbols(rom: Path) -> dict[str, int]:
    out = {}
    for m in re.finditer(r"DEF (\S+) 0x([0-9A-Fa-f]+)", rom.with_suffix(".noi").read_text()):
        out[m.group(1)] = int(m.group(2), 16)
    return out


def run_slice(task: dict) -> dict:
    from quintra_pyboy_env import QuintraPyBoyEnv
    from run_pyboy_checkpoints import controller_action

    rom = Path(task["rom"])
    syms = noi_symbols(rom)
    status_addr, ticks_addr = syms["_player_status_kind"], syms["_player_status_ticks"]
    env = QuintraPyBoyEnv(rom)
    try:
        obs = env.load_state(task["state"])
        mem = env.pb.memory
        entities = env.addrs["_entities"]
        human = HumanFilter(task["skill"], task["seed"], task["cls"])
        # Seed the cartridge-independent variety: a few idle frames before
        # the first decision, chosen by the seed, desynchronise enemy phase.
        for _ in range(task["seed"] % 7):
            obs, _, _, _ = env.step(0, 1)
        kind, cap = task["kind"], task["frames"]
        giants = [e for e in obs["hostiles"] if e["giant"]]
        boss_start = giants[0]["hp"] if giants else 0
        boss_last = boss_start
        before_bosses = obs["bosses"]
        hp_start = last_hp = hp_min = obs["hp"]
        row = dict(skill=task["skill"], seed=task["seed"], hero=CHAMPIONS[task["cls"]],
                   cls=task["cls"], stage=task["stage"], kind=kind,
                   difficulty=obs["difficulty"])
        dmg = dealt = hits = spikes = burst_max = 0
        lands = harmful = in_boss = low_hp = exposed = 0
        kinds: dict[str, int] = {}
        hit_log: list[tuple[int, int]] = []
        in_spike = False
        last_status = last_ticks = 0
        last_harm = (0, -1)
        enemy_hp: dict[int, tuple[int, int]] = {}
        seen_hostile = False
        clear_frames = 0
        outcome = "timeout"
        frame = 0
        burst = 0
        while frame < cap:
            hidden = human.scan(mem, entities, frame)
            view = obs
            blind = human.p and mem[status_addr] == 5
            if hidden or blind:
                # Blind darkens the screen for a person; a RAM-reading pilot
                # would not notice, so blinded humans only see shots nearby.
                view = dict(obs)
                view["projectiles"] = [s for s in obs["projectiles"]
                                       if (s["x"], s["y"]) not in hidden and not (
                                           blind and max(abs(s["x"] - obs["x"]),
                                                         abs(s["y"] - obs["y"])) > 32)]
            threatened = bool(view["projectiles"]) or any(
                max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])) <= 40
                for e in obs["hostiles"])
            action = human.apply(controller_action(view, frame), threatened)
            obs, _, terminal, _ = env.step(action, 1)
            frame += 1
            hp, hp_max = obs["hp"], obs["hp_max"]
            boss_alive = any(e["giant"] for e in obs["hostiles"])
            if boss_alive:
                boss_last = next(e["hp"] for e in obs["hostiles"] if e["giant"])
            if hp < last_hp:
                taken = last_hp - hp
                dmg += taken
                hits += 1
                hit_log.append((frame, taken))
            last_hp = hp
            hp_min = min(hp_min, hp)
            hit_log = [h for h in hit_log if frame - h[0] < BURST_WINDOW]
            burst = sum(h[1] for h in hit_log)
            burst_max = max(burst_max, burst)
            spike = hp_max > 0 and burst >= hp_max * BURST_SPIKE_FRACTION
            if spike and not in_spike:
                spikes += 1
            in_spike = spike
            st, ticks = mem[status_addr], mem[ticks_addr]
            if 0 < st < len(STATUS_NAMES) and (st != last_status or ticks > last_ticks):
                lands += 1
                name = STATUS_NAMES[st]
                kinds[name] = kinds.get(name, 0) + 1
                if st in HARMFUL:
                    harmful += 1
                    in_boss += boss_alive
                    low_hp += hp_max > 0 and hp <= hp_max * LOW_HP_FRACTION
                    last_harm = (st, frame)
            last_status, last_ticks = st, ticks
            if st in HARMFUL or (last_harm[1] >= 0 and frame - last_harm[1] < STATUS_WINDOW):
                exposed += 1
            for slot in range(32):
                base = entities + slot * 28
                if mem[base] == 2 and (mem[base + 1] & 1):
                    kind_id, ehp = mem[base + 17], mem[base + 14]
                    prev = enemy_hp.get(slot)
                    if prev and prev[0] == kind_id and ehp < prev[1]:
                        dealt += prev[1] - ehp
                    enemy_hp[slot] = (kind_id, ehp)
                elif slot in enemy_hp:
                    if enemy_hp[slot][1] <= 2:
                        dealt += enemy_hp[slot][1]
                    del enemy_hp[slot]
            if kind == "boss" and obs["bosses"] > before_bosses:
                outcome = "cleared"
                break
            if hp == 0 or terminal:
                outcome = "won" if obs["victory"] else "died"
                break
            if kind == "entry":
                live = [e for e in obs["hostiles"] if not e["giant"]]
                seen_hostile |= bool(live)
                clear_frames = clear_frames + 1 if (seen_hostile and not live) else 0
                if clear_frames >= 30:
                    outcome = "cleared"
                    frame -= 30
                    break
                if not seen_hostile and frame >= 600:
                    outcome = "empty"
                    break
        died = outcome == "died"
        row.update(outcome=outcome, frames=frame, dmg_taken=dmg, dmg_dealt=dealt,
                   hits=hits, hp_start=hp_start, hp_end=obs["hp"], hp_min=hp_min,
                   hp_max=obs["hp_max"], boss_hp_start=boss_start,
                   boss_hp_end=0 if outcome == "cleared" and kind == "boss" else boss_last,
                   burst_max_2s=burst_max, burst_spikes=spikes, status_lands=lands,
                   status_harmful=harmful, status_in_boss=in_boss, status_low_hp=low_hp,
                   status_kinds=";".join(f"{k}:{v}" for k, v in sorted(kinds.items())),
                   death_status_kind=STATUS_NAMES[last_harm[0]] if died and last_harm[1] >= 0 else "",
                   death_status_age=frame - last_harm[1] if died and last_harm[1] >= 0 else -1,
                   death_status_active=STATUS_NAMES[last_status] if died and last_status in HARMFUL else "",
                   death_burst_2s=burst if died else 0,
                   missed_dodges=human.missed, lapses=human.lapses,
                   status_exposed_frames=exposed)
        row["class"] = row.pop("cls")
        return row
    finally:
        env.close()


def parse_stages(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, default=ROOT / "rom/working/quintra.gbc")
    ap.add_argument("--state-dir", type=Path, default=ROOT / "tmp/stage-states")
    ap.add_argument("--skills", nargs="+", default=["nonexpert", "average", "skilled"],
                    choices=SKILLS)
    ap.add_argument("--heroes", nargs="+", default=list(CHAMPIONS), choices=CHAMPIONS)
    ap.add_argument("--stages", default="1-9")
    ap.add_argument("--kinds", nargs="+", default=["boss", "entry"], choices=("boss", "entry"))
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=1)
    ap.add_argument("--difficulty", choices=("normal", "easy"), default="normal")
    ap.add_argument("--boss-frames", type=int, default=10800)
    ap.add_argument("--room-frames", type=int, default=3600)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", type=Path, default=ROOT / "tmp/balance/arena.csv")
    args = ap.parse_args()
    suffix = "-easy" if args.difficulty == "easy" else ""
    tasks = []
    for skill in args.skills:
        for hero in args.heroes:
            for stage in parse_stages(args.stages):
                for kind in args.kinds:
                    state = args.state_dir / f"quintra-stage-{stage:02d}-{kind}-{hero}{suffix}.pyboy"
                    if not state.exists():
                        raise SystemExit(f"missing {state}; run make_stage_states.py first")
                    for i in range(args.seeds):
                        tasks.append(dict(rom=str(args.rom), state=str(state), skill=skill,
                                          cls=CHAMPIONS.index(hero), stage=stage, kind=kind,
                                          seed=args.seed_base + i,
                                          frames=args.boss_frames if kind == "boss" else args.room_frames))
    started = time.time()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    # Rows stream to the CSV as slices finish, so a long sweep can be read
    # (or reported on) before it ends.
    with args.out.open("w", newline="") as f, ProcessPoolExecutor(max_workers=args.jobs) as pool:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        futures = [pool.submit(run_slice, t) for t in tasks]
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            rows.append(r)
            w.writerow({k: r[k] for k in FIELDS})
            f.flush()
            if n % 50 == 0 or n == len(tasks):
                print(f"[arena] {n}/{len(tasks)} slices, {round(time.time() - started)}s", flush=True)
    meta = {"rom_sha256": json.loads((args.state_dir / "manifest.json").read_text()).get("rom_sha256"),
            "slices": len(rows), "seconds": round(time.time() - started),
            "skills": args.skills, "heroes": args.heroes, "stages": parse_stages(args.stages),
            "kinds": args.kinds, "seeds": args.seeds, "difficulty": args.difficulty}
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"[arena] {len(rows)} slices in {meta['seconds']}s -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
