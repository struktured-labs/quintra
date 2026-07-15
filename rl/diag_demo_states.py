"""Probe each user demo state to detect hangs.

Loads each .state file and runs N random steps measuring step rate.
States that step slowly (<200 steps/sec) are flagged as broken.

Uses subprocess + per-state hard timeout so a hanging state doesn't block the survey.
"""
from __future__ import annotations
import os, sys, time, glob, subprocess, json

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
CONVERTED = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/user_demo/converted"
STEPS_PER_PROBE = 100
SLOW_THRESHOLD_SPS = 200.0
PROBE_TIMEOUT = 30  # seconds per state

def probe_in_process(state_path: str) -> dict:
    sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
    import numpy as np
    from penta_rl.env import PentaEnv, N_ACTIONS
    env = PentaEnv(ROM, max_steps=4096, savestate_path=state_path)
    obs, info = env.reset()
    s0 = info["state"]
    rng = np.random.default_rng(42)
    t0 = time.time()
    n_steps = 0
    n_terminated = 0
    n_truncated = 0
    for _ in range(STEPS_PER_PROBE):
        a = int(rng.integers(0, N_ACTIONS))
        obs, rew, term, trunc, info = env.step(a)
        n_steps += 1
        if term:
            n_terminated += 1
            obs, info = env.reset()
        elif trunc:
            n_truncated += 1
            obs, info = env.reset()
    dt = time.time() - t0
    sps = n_steps / dt if dt > 0 else 0.0
    s_end = info["state"]
    env.close()
    return {
        "name": os.path.basename(state_path),
        "init_FFBA": s0.level, "init_D880": s0.scene, "init_FFBD": s0.room,
        "init_FFBF": s0.miniboss,
        "steps_per_sec": round(sps, 1),
        "elapsed_s": round(dt, 2),
        "n_terminated": n_terminated,
        "n_truncated": n_truncated,
        "end_FFBA": s_end.level, "end_D880": s_end.scene,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        # Subprocess probe mode: print JSON result
        result = probe_in_process(sys.argv[2])
        print("RESULT_JSON=" + json.dumps(result))
        sys.exit(0)
    states = sorted(glob.glob(f"{CONVERTED}/*.state"))
    print(f"Probing {len(states)} demo states ({STEPS_PER_PROBE} random steps each, {PROBE_TIMEOUT}s timeout)...\n", flush=True)
    print(f"{'state':<45} {'FFBA':>5} {'D880':>5} {'FFBD':>5} {'FFBF':>5} {'sps':>8} {'time':>6} {'term':>5} {'trunc':>6}")
    print("-" * 110)
    slow = []
    hung = []
    for sp in states:
        cmd = [sys.executable, __file__, "--probe", sp]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
            if out.returncode != 0:
                print(f"{os.path.basename(sp):<45} CRASH: {out.stderr.splitlines()[-1] if out.stderr else 'unknown'}", flush=True)
                continue
            line = next((l for l in out.stdout.splitlines() if l.startswith("RESULT_JSON=")), None)
            if line is None:
                print(f"{os.path.basename(sp):<45} NO_RESULT", flush=True)
                continue
            r = json.loads(line[len("RESULT_JSON="):])
            mark = " SLOW" if r["steps_per_sec"] < SLOW_THRESHOLD_SPS else ""
            if r["steps_per_sec"] < SLOW_THRESHOLD_SPS:
                slow.append(r)
            print(f"{r['name']:<45} {r['init_FFBA']:>5} 0x{r['init_D880']:02x} {r['init_FFBD']:>5} {r['init_FFBF']:>5} {r['steps_per_sec']:>8.1f} {r['elapsed_s']:>6.2f} {r['n_terminated']:>5} {r['n_truncated']:>6}{mark}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"{os.path.basename(sp):<45} HANG (>{PROBE_TIMEOUT}s) — broken state", flush=True)
            hung.append(os.path.basename(sp))
    if slow:
        print(f"\n{len(slow)} SLOW states (< {SLOW_THRESHOLD_SPS} sps):")
        for r in slow:
            print(f"  {r['name']}: {r['steps_per_sec']:.1f} sps")
    if hung:
        print(f"\n{len(hung)} HUNG states (timed out at {PROBE_TIMEOUT}s):")
        for n in hung:
            print(f"  {n}")
