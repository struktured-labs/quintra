#!/usr/bin/env python3
"""Headless human-skill balance sweep for Quintra.

Runs the mGBA controller (scripts/quintra_balance_bot.lua) with the human
model (scripts/quintra_human_model.lua) at one or more skill tiers, in
parallel, and collects one CSV row per stage reached.

Two modes:
  full   cold boot, pick a hero, play until death, victory, or --frames.
         Gives real run-death distributions and item/resource curves.
  slice  cold boot through the title's Rift Index stage warp (the cartridge's
         own stage-ready build) and stop after that stage's Colossus falls.
         Measures every stage, even ones a weak tier never reaches.

Outputs in --out: stages.csv, status.csv, runs.csv, sweep.json.
Then run scripts/balance_report.py on the same directory.

Example (see scripts/balance_full_sweep.sh):
  python3 scripts/balance_sweep.py --mode slice --skills nonexpert average \
      --classes 0 1 2 3 4 --seeds 4 --stages 1-9 --jobs 16 --out tmp/balance/slice
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
SKILLS = ("bot", "skilled", "average", "nonexpert")
ADDR_ENV = {
    "QUINTRA_RS_ADDR": "_run_state", "QUINTRA_PL_ADDR": "_player",
    "QUINTRA_EN_ADDR": "_entities", "QUINTRA_TM_ADDR": "_room_tilemap",
    "QUINTRA_WORLD_EXT_ADDR": "_room_world_extension",
    "QUINTRA_WORLD_BOTTOM_ADDR": "_room_world_bottom",
    "QUINTRA_WORLD_WIDTH_ADDR": "_room_world_width",
    "QUINTRA_WORLD_HEIGHT_ADDR": "_room_world_height",
    "QUINTRA_CAMERA_X_ADDR": "_room_camera_x",
    "QUINTRA_CAMERA_Y_ADDR": "_room_camera_y",
    "QUINTRA_SCREEN_ADDR": "_loop_current_screen",
    "QUINTRA_FRAME_ADDR": "_loop_frame_counter",
    "QUINTRA_HITSTOP_ADDR": "_g_hitstop",
    "QUINTRA_SEALED_ADDR": "_room_combat_sealed",
    "QUINTRA_PUZZLE_KIND_ADDR": "_room_puzzle_kind",
    "QUINTRA_PUZZLE_LOCKED_ADDR": "_room_puzzle_locked",
    "QUINTRA_CINDER_OPEN_ADDR": "_cinder_damage_open",
}
STATUS_HEADER = "skill,run,class,stage,frame,status,in_boss,low_hp,hp,hp_max"


def stage_header() -> str:
    text = (ROOT / "scripts/quintra_human_model.lua").read_text()
    m = re.search(r'QH_STAGE_HEADER = "([^"]+)"', text)
    if not m:
        raise SystemExit("QH_STAGE_HEADER missing from quintra_human_model.lua")
    return m.group(1)


def balance_header() -> str:
    out = subprocess.run(
        ["bash", "-c", f"source {ROOT}/scripts/balance_csv_header.sh && quintra_balance_csv_header"],
        check=True, capture_output=True, text=True)
    return out.stdout.strip()


def symbols(noi: Path) -> dict[str, str]:
    text = noi.read_text()
    env = {}
    for key, name in ADDR_ENV.items():
        m = re.search(rf"DEF {re.escape(name)} (0x[0-9A-Fa-f]+)", text)
        env[key] = str(int(m.group(1), 16)) if m else "0"
    return env


def parse_stages(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def run_one(job: dict) -> dict:
    work = Path(job["work"])
    work.mkdir(parents=True, exist_ok=True)
    tag = job["tag"]
    csv = work / f"{tag}.run.csv"
    stages = work / f"{tag}.stages.csv"
    status = work / f"{tag}.status.csv"
    for p in (csv, stages, status):
        p.unlink(missing_ok=True)
    csv.write_text(job["balance_header"] + "\n")
    save_dir = work / f"{tag}.sav"
    save_dir.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(job["addr_env"])
    env.update({
        "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
        "QUINTRA_NOI_PATH": job["noi"],
        "QUINTRA_BOT_RUN": str(job["run"]), "QUINTRA_BOT_CLASS": str(job["cls"]),
        "QUINTRA_BOT_FRAMES": str(job["frames"]), "QUINTRA_BOT_OUT": str(csv),
        "QUINTRA_BOT_SKILL": job["skill"], "QUINTRA_BOT_MODE": job["mode"],
        "QUINTRA_STAGELOG_OUT": str(stages), "QUINTRA_STATUSLOG_OUT": str(status),
        "QUINTRA_BOT_WATCHDOG_SECONDS": str(job.get("watchdog", 5)),
        "QUINTRA_BOT_HANG_OUT": str(work / f"{tag}.hang.txt"),
    })
    if job["easy"]:
        env["QUINTRA_BOT_EASY"] = "1"
    if job.get("debug"):
        env["QUINTRA_BOT_DEBUG"] = "1"
        env["QUINTRA_BOT_DEBUG_OUT"] = str(work / f"{tag}.debug.log")
    cmd = [job["mgba"], "-C", f"savegamePath={save_dir}"]
    if job["mode"] == "slice":
        env["QUINTRA_BOT_WARP_STAGE"] = str(job["stage"])
        env["QUINTRA_BOT_STOP_AFTER_CLEARS"] = "1"
    cmd += [job["rom"], "--script", str(ROOT / "scripts/quintra_balance_bot.lua"), "-l", "0"]
    start = time.monotonic()
    log = work / f"{tag}.log"
    with log.open("wb") as lf:
        proc = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        # mgba-headless exits when the Lua script returns, but some builds
        # linger; the committed CSV row is the completion boundary.
        done = False
        while time.monotonic() - start < job["timeout"]:
            if proc.poll() is not None:
                break
            if (work / f"{tag}.hang.txt").exists():
                time.sleep(0.5)
                break
            if csv.stat().st_size > len(job["balance_header"]) + 1:
                done = True
                time.sleep(0.2)
                break
            time.sleep(0.5)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    lines = csv.read_text().splitlines()
    ok = len(lines) >= 2
    return {"tag": tag, "ok": ok, "seconds": round(time.monotonic() - start, 1),
            "run_row": lines[1] if ok else "",
            "stages": stages.read_text().splitlines() if stages.exists() else [],
            "status": status.read_text().splitlines() if status.exists() else [],
            "hang": (work / f"{tag}.hang.txt").read_text() if (work / f"{tag}.hang.txt").exists() else "",
            "job": {k: job[k] for k in ("skill", "run", "cls", "mode", "stage")}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(ROOT / "rom/working/quintra.gbc"))
    ap.add_argument("--mode", choices=("full", "slice"), default="full")
    ap.add_argument("--skills", nargs="+", default=["nonexpert", "average", "skilled"], choices=SKILLS)
    ap.add_argument("--classes", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--seeds", type=int, default=3, help="seed count per (skill, hero[, stage])")
    ap.add_argument("--seed-base", type=int, default=1)
    ap.add_argument("--stages", default="1-9", help="slice mode: e.g. 1-9 or 3")
    ap.add_argument("--frames", type=int, default=108000, help="frame cap per run (full) or per slice")
    ap.add_argument("--difficulty", choices=("normal", "easy"), default="normal")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument("--timeout", type=float, default=1800, help="host seconds per job")
    ap.add_argument("--mgba", default=os.environ.get("QUINTRA_MGBA_BIN", "mgba-headless"))
    ap.add_argument("--debug", action="store_true", help="write the controller's event log per job")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rom = Path(args.rom).resolve()
    noi = rom.with_suffix(".noi")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sweep-", dir=out))
    base = {"rom": str(rom), "noi": str(noi), "addr_env": symbols(noi), "mgba": args.mgba,
            "balance_header": balance_header(), "frames": args.frames,
            "timeout": args.timeout, "easy": args.difficulty == "easy",
            "mode": args.mode, "work": str(work), "debug": args.debug}
    jobs = []
    stages = parse_stages(args.stages) if args.mode == "slice" else [0]
    for skill in args.skills:
        for cls in args.classes:
            for stage in stages:
                for i in range(args.seeds):
                    run = args.seed_base + i
                    job = dict(base, skill=skill, cls=cls, run=run, stage=stage,
                               tag=f"{skill}-c{cls}-s{stage}-r{run}")
                    jobs.append(job)
    started = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for res in pool.map(run_one, jobs):
            results.append(res)
    hdr = stage_header()
    with (out / "stages.csv").open("w") as f:
        f.write(hdr + "\n")
        for r in results:
            for line in r["stages"]:
                f.write(line + "\n")
    with (out / "status.csv").open("w") as f:
        f.write(STATUS_HEADER + "\n")
        for r in results:
            for line in r["status"]:
                f.write(line + "\n")
    with (out / "runs.csv").open("w") as f:
        f.write("skill,mode,stage_start," + base["balance_header"] + "\n")
        for r in results:
            if r["ok"]:
                f.write(f'{r["job"]["skill"]},{r["job"]["mode"]},{r["job"]["stage"]},{r["run_row"]}\n')
    failed = [r["tag"] for r in results if not r["ok"] or not r["stages"]]
    hangs = {r["tag"]: r["hang"].splitlines()[:12] for r in results if r["hang"]}
    meta = {"rom_sha256": subprocess.run(["sha256sum", str(rom)], capture_output=True, text=True).stdout.split()[0],
            "mode": args.mode, "skills": args.skills, "classes": args.classes, "seeds": args.seeds,
            "stages": stages, "frames": args.frames, "difficulty": args.difficulty,
            "jobs": len(jobs), "failed": failed, "wall_seconds": round(time.time() - started),
            "hangs": hangs,
            "job_seconds": {r["tag"]: r["seconds"] for r in results}}
    (out / "sweep.json").write_text(json.dumps(meta, indent=2))
    print(f"[sweep] {args.mode}: {len(jobs)} jobs, {len(failed)} failed, "
          f"{meta['wall_seconds']}s -> {out}")
    if failed:
        print("[sweep] failed: " + " ".join(failed[:12]), file=sys.stderr)
    return 1 if len(failed) > len(jobs) // 4 else 0


if __name__ == "__main__":
    sys.exit(main())
