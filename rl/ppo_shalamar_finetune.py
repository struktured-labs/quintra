"""PPO fine-tune from bc_combined_best on Shalamar arena with dense reward.

Uses the new stage_boss_damage reward (+2/HP, phase milestones, low-HP kill signal).
Starts every episode from BOSS1_SHALAMAR_pre_fight.state under godmode.
"""
from __future__ import annotations
import os, sys, time, json
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import torch
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.env import N_ACTIONS, ACTION_BUTTONS, PentaEnv
from penta_rl.godmode_env import godmode_step
from penta_rl.state import vector_dim, read_state, state_to_vector
from penta_rl.ppo import PPOAgent, PPOConfig, TrajectoryBuffer

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
STATE = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/user_demo/converted/195329_BOSS1_SHALAMAR_pre_fight.state"
WARM_START = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_combined_kill_best.pt"
OUT_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl"

EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
STEPS_PER_EPOCH = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
LABEL = sys.argv[3] if len(sys.argv) > 3 else "ppo_shalamar_v1"


class ShalamarEnv(PentaEnv):
    """PentaEnv with per-tick godmode and termination on success / low-HP kill signal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_ffba = 0
        self._reached_low_hp = False

    def reset(self, seed=None, options=None):
        obs, info = super().reset(seed=seed, options=options)
        self._init_ffba = info["state"].level
        self._reached_low_hp = False
        return obs, info

    def step(self, action: int):
        for b in self._held:
            self.pb.button_release(b)
        self._held = ACTION_BUTTONS[action]
        for b in self._held:
            self.pb.button_press(b)
        for _ in range(self.frame_skip):
            godmode_step(self.pb)
            self.pb.tick()
        self.steps += 1
        s = read_state(self.pb)
        reward, info = self.reward_tracker.step(s, action=action)
        truncated = self.steps >= self.max_steps
        terminated = False
        # Success: FFBA advance OR low-HP kill credited by reward tracker
        if s.level > self._init_ffba:
            terminated = True
            info["success"] = True
            info["success_kind"] = "ffba_advance"
        elif self.reward_tracker.stage_boss_low_hp_credited:
            terminated = True
            info["success"] = True
            info["success_kind"] = "low_hp_kill"
        info["state"] = s
        info["steps"] = self.steps
        return state_to_vector(s), reward, terminated, truncated, info


def run():
    device = "cpu"
    obs_dim = vector_dim()
    cfg = PPOConfig(epochs=EPOCHS, steps_per_epoch=STEPS_PER_EPOCH,
                    train_iters=10, entropy_coef=0.02, pi_lr=1e-4, v_lr=5e-4)
    agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device=device)
    warm = torch.load(WARM_START, map_location=device, weights_only=False)
    agent.net.load_state_dict(warm["model"])
    print(f"Warm-started from {WARM_START}", flush=True)

    env = ShalamarEnv(ROM, max_steps=2400, savestate_path=STATE)
    rng = np.random.default_rng(20260510)
    obs, info = env.reset()
    print(f"  start: D880=0x{info['state'].scene:02x} FFBA={info['state'].level} "
          f"DCBB={info['state'].boss_hp}", flush=True)

    metrics = []
    completed_returns = []
    n_success_total = 0
    t0 = time.time()

    def save_ckpt(epoch):
        save_path = f"{OUT_DIR}/ppo_shalamar_{LABEL}_ep{epoch}.pt"
        torch.save({"model": agent.net.state_dict(), "metrics": metrics,
                    "epoch": epoch, "warm_start": WARM_START}, save_path)
        latest = f"{OUT_DIR}/ppo_shalamar_{LABEL}_latest.pt"
        if os.path.lexists(latest):
            os.unlink(latest)
        os.symlink(save_path, latest)

    for ep in range(EPOCHS):
        buf = TrajectoryBuffer(obs_dim, STEPS_PER_EPOCH)
        ep_reward = 0.0
        n_done = 0
        n_success = 0
        min_dcbb_in_ep = 0xFF
        for t in range(STEPS_PER_EPOCH):
            with torch.no_grad():
                x = torch.from_numpy(obs).float().unsqueeze(0)
                logits, v = agent.net(x)
            arr = logits.numpy().flatten()
            p = np.exp(arr - arr.max()); p /= p.sum()
            a = int(rng.choice(N_ACTIONS, p=p))
            lp = float(np.log(p[a] + 1e-10))
            obs2, rew, term, trunc, info = env.step(a)
            done = term or trunc
            buf.store(obs, a, float(rew), float(v.item()), lp, done)
            ep_reward += float(rew)
            if 0x0C <= info["state"].scene <= 0x14:
                min_dcbb_in_ep = min(min_dcbb_in_ep, info["state"].boss_hp)
            if done:
                n_done += 1
                completed_returns.append(ep_reward)
                if info.get("success"):
                    n_success += 1
                    n_success_total += 1
                    print(f"  *** SUCCESS *** ep_reward={ep_reward:.2f} kind={info.get('success_kind')}", flush=True)
                ep_reward = 0.0
                obs, info = env.reset()
                min_dcbb_in_ep = 0xFF
            else:
                obs = obs2
        with torch.no_grad():
            x = torch.from_numpy(obs).float().unsqueeze(0)
            _, last_val = agent.net(x)
        data = buf.finish(cfg.gamma, cfg.lam, last_val=float(last_val.item()))
        losses = agent.update(data)

        recent = completed_returns[-10:] or [0.0]
        elapsed = time.time() - t0
        m = {"epoch": ep+1, "elapsed_s": round(elapsed, 1), "n_eps": n_done,
             "n_success_chunk": n_success, "n_success_total": n_success_total,
             "mean_return": round(float(np.mean(recent)), 2),
             "max_return": round(float(max(recent)), 2),
             "min_dcbb": int(min_dcbb_in_ep) if min_dcbb_in_ep != 0xFF else None,
             "loss_pi": round(losses["pi"], 4), "loss_v": round(losses["v"], 4),
             "entropy": round(losses["ent"], 4)}
        metrics.append(m)
        print(f"ep {ep+1:3d}/{EPOCHS}  eps={n_done:2d}  ret={m['mean_return']:7.2f}  "
              f"max={m['max_return']:7.2f}  success={n_success_total}  "
              f"min_dcbb={m['min_dcbb']}  ent={m['entropy']:.3f}  t={elapsed:.0f}s", flush=True)
        if (ep+1) % 5 == 0 or ep+1 == EPOCHS:
            save_ckpt(ep+1)
    env.close()
    with open(f"{OUT_DIR}/ppo_shalamar_{LABEL}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nTotal successes: {n_success_total}")
    print(f"Saved: {OUT_DIR}/ppo_shalamar_{LABEL}_latest.pt")


if __name__ == "__main__":
    run()
