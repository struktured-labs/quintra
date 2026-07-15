"""Evaluate BC kill-oversampled checkpoint vs v19 baseline.

Runs N episodes from each test state with each policy, reports kill rate.
"""
from __future__ import annotations
import os, sys, time
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import torch
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.env import N_ACTIONS, PentaEnv
from penta_rl.state import vector_dim, read_state, state_to_vector
from penta_rl.ppo import PPOAgent, PPOConfig

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
EP_PER_STATE = 10
MAX_STEPS = 2400  # Shalamar drain takes ~2155 steps; mini-bosses ~200

CHECKPOINTS = {
    "ppo_shalamar_v2":     "/home/struktured/projects/penta-dragon-dx-claude/rl/ppo_shalamar_v2_latest.pt",
    "bc_combined_best":    "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_combined_kill_best.pt",
    "v19_ep200":           "/home/struktured/projects/penta-dragon-dx-claude/rl/ppo_v19_resume18_ep200.pt",
}
TEST_STATES = [
    "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/gargoyle.state",
    "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/spider.state",
    "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/user_demo/converted/195329_BOSS1_SHALAMAR_pre_fight.state",
]


def load_ckpt(path):
    obs_dim = vector_dim()
    cfg = PPOConfig()
    agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device="cpu")
    state = torch.load(path, map_location="cpu", weights_only=False)
    agent.net.load_state_dict(state["model"])
    agent.net.eval()
    return agent


def policy_step(agent, obs, deterministic=False, rng=None):
    with torch.no_grad():
        x = torch.from_numpy(obs).float().unsqueeze(0)
        logits, v = agent.net(x)
    arr = logits.numpy().flatten()
    if deterministic:
        return int(np.argmax(arr))
    p = np.exp(arr - arr.max()); p /= p.sum()
    return int(rng.choice(N_ACTIONS, p=p))


def run_eval(agent_name, agent, state_path, n_eps, deterministic, rng):
    from penta_rl.godmode_env import godmode_step
    is_shalamar = "SHALAMAR" in state_path
    env = PentaEnv(ROM, max_steps=MAX_STEPS, savestate_path=state_path)
    n_kills = 0
    n_kill_eps = 0
    n_shalamar_kills = 0  # actually drained boss to near-zero in arena
    shalamar_dcbb_mins = []
    returns = []
    survives = 0
    for ep in range(n_eps):
        obs, info = env.reset()
        prev_ffbf = info["state"].miniboss
        ep_kills = 0
        ep_ret = 0.0
        arena_dcbb_min = 0xFF  # min DCBB while in stage arena this episode
        for step in range(MAX_STEPS):
            if is_shalamar:
                godmode_step(env.pb)
            a = policy_step(agent, obs, deterministic, rng)
            obs, r, term, trunc, info = env.step(a)
            ep_ret += r
            cur = info["state"].miniboss
            cur_d880 = info["state"].scene
            cur_dcbb = info["state"].boss_hp
            if prev_ffbf != 0 and cur == 0:
                ep_kills += 1
                n_kills += 1
            if is_shalamar and 0x0c <= cur_d880 <= 0x14:
                arena_dcbb_min = min(arena_dcbb_min, cur_dcbb)
            prev_ffbf = cur
            if term or trunc: break
        if is_shalamar:
            shalamar_dcbb_mins.append(arena_dcbb_min)
            if arena_dcbb_min <= 15:    # real boss-drain threshold
                n_shalamar_kills += 1
        returns.append(ep_ret)
        if ep_kills > 0: n_kill_eps += 1
        if step >= MAX_STEPS - 1: survives += 1
    env.close()
    out = {"name": agent_name, "state": os.path.basename(state_path),
           "n_eps": n_eps, "n_kills": n_kills + n_shalamar_kills,
           "kill_eps": n_kill_eps + n_shalamar_kills,
           "mean_return": float(np.mean(returns)),
           "max_return": float(max(returns)),
           "survives": survives}
    if is_shalamar:
        out["shalamar_dcbb_mins"] = shalamar_dcbb_mins
    return out


def main():
    rng = np.random.default_rng(20260509)
    print(f"Evaluating {len(CHECKPOINTS)} policies × {len(TEST_STATES)} states × {EP_PER_STATE} eps each (sample)\n", flush=True)
    print(f"{'policy':<24} {'state':<60} {'n_kills':>8} {'kill_eps':>9} {'mean_ret':>9} {'max_ret':>9} {'survives':>9}")
    print("-" * 140)
    rows = []
    for name, ckpt_path in CHECKPOINTS.items():
        if not os.path.exists(ckpt_path):
            print(f"  Missing: {ckpt_path}")
            continue
        agent = load_ckpt(ckpt_path)
        for sp in TEST_STATES:
            r = run_eval(name, agent, sp, EP_PER_STATE, deterministic=False, rng=rng)
            rows.append(r)
            extra = f"  dcbb_mins={r['shalamar_dcbb_mins']}" if "shalamar_dcbb_mins" in r else ""
            print(f"{r['name']:<24} {r['state']:<60} {r['n_kills']:>8} {r['kill_eps']:>9} "
                  f"{r['mean_return']:>9.1f} {r['max_return']:>9.1f} {r['survives']:>9}{extra}", flush=True)
    print()
    # Aggregated by policy
    by_policy = {}
    for r in rows:
        by_policy.setdefault(r["name"], {"kills": 0, "kill_eps": 0, "eps": 0, "ret": 0})
        by_policy[r["name"]]["kills"] += r["n_kills"]
        by_policy[r["name"]]["kill_eps"] += r["kill_eps"]
        by_policy[r["name"]]["eps"] += r["n_eps"]
        by_policy[r["name"]]["ret"] += r["mean_return"] * r["n_eps"]
    print("=== Summary ===")
    for name, d in by_policy.items():
        kr = d["kills"] / d["eps"] if d["eps"] else 0
        ker = d["kill_eps"] / d["eps"] if d["eps"] else 0
        ar = d["ret"] / d["eps"] if d["eps"] else 0
        print(f"  {name:<24} {d['kills']:>3} kills / {d['eps']:>2} eps  ({kr*100:.1f}%)  "
              f"kill_eps={d['kill_eps']}/{d['eps']} ({ker*100:.1f}%)  avg_ret={ar:.1f}")


if __name__ == "__main__":
    main()
