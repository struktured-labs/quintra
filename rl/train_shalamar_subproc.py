"""Train PPO with env running in a subprocess (multiprocessing).

Avoids torch+PyBoy interaction by isolating env in a separate process.
Main process owns torch agent. Worker process owns env.
"""
from __future__ import annotations
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import json, sys, time
import multiprocessing as mp
import numpy as np

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SHALAMAR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum/arena_FFBA1_D880_0xd_FFD3_4.state"
OUT_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl"


from penta_rl.env_worker import env_worker


def main(epochs=100, steps_per_epoch=1024, label="shalamar_sp"):
    import torch
    from penta_rl.env import N_ACTIONS
    from penta_rl.state import vector_dim
    from penta_rl.ppo import PPOAgent, PPOConfig, TrajectoryBuffer

    device = "cpu"
    print(f"Device: {device}, epochs={epochs}, steps/epoch={steps_per_epoch}", flush=True)

    cmd_q = mp.Queue()
    res_q = mp.Queue()
    worker = mp.Process(target=env_worker, args=(cmd_q, res_q))
    worker.start()

    # First message from worker is initial reset state
    obs, _, _, info = res_q.get()
    init_ffba = info["level"]
    print(f"Initial: FFBA={init_ffba} D880={hex(info['scene'])}", flush=True)

    obs_dim = vector_dim()
    cfg = PPOConfig(epochs=epochs, steps_per_epoch=steps_per_epoch,
                    train_iters=10, entropy_coef=0.03)
    agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device=device)

    completed_returns = []
    ffba_advances = 0
    metrics = []
    t_start = time.time()
    rng = np.random.default_rng(0)

    for ep in range(epochs):
        buf = TrajectoryBuffer(obs_dim, steps_per_epoch)
        n_done = 0
        ep_reward = 0.0
        for t in range(steps_per_epoch):
            with torch.no_grad():
                o = torch.from_numpy(obs).float().unsqueeze(0)
                logits, vals = agent.net(o)
                probs = torch.softmax(logits, dim=-1).numpy().squeeze()
            a = int(rng.choice(N_ACTIONS, p=probs))
            lp = float(np.log(probs[a] + 1e-10))
            v = float(vals.item())

            cmd_q.put(a)
            obs2, rew, done, info2 = res_q.get()

            buf.store(obs, a, rew, v, lp, done)
            ep_reward += rew
            if info2["level"] > init_ffba:
                ffba_advances += 1
                print(f"  *** FFBA ADVANCE *** ep={n_done+1} reward={ep_reward:.2f}", flush=True)
                done = True
            if done:
                n_done += 1
                completed_returns.append(ep_reward)
                ep_reward = 0.0
                cmd_q.put("reset")
                obs, _, _, _ = res_q.get()
            else:
                obs = obs2

        with torch.no_grad():
            o = torch.from_numpy(obs).float().unsqueeze(0)
            _, last_v = agent.net(o)
            last_val = float(last_v.item())
        data = buf.finish(cfg.gamma, cfg.lam, last_val=last_val)
        losses = agent.update(data)

        recent = completed_returns[-20:] or [0.0]
        elapsed = time.time() - t_start
        m = {
            "epoch": ep + 1, "elapsed_s": round(elapsed, 1),
            "n_eps": len(completed_returns),
            "mean_return": round(float(np.mean(recent)), 2),
            "max_return": round(float(max(recent)), 2),
            "ffba_advances": ffba_advances,
            "loss_pi": round(losses["pi"], 4),
            "loss_v": round(losses["v"], 4),
            "entropy": round(losses["ent"], 4),
        }
        metrics.append(m)
        print(f"ep {ep+1:3d}/{epochs}  eps={len(completed_returns):4d}  "
              f"ret={m['mean_return']:7.2f}  max={m['max_return']:7.2f}  "
              f"adv={ffba_advances}  ent={m['entropy']:.3f}  t={elapsed:.0f}s", flush=True)

        if (ep + 1) % 25 == 0:
            ckpt = f"{OUT_DIR}/ppo_{label}_ep{ep+1}.pt"
            torch.save({"model": agent.net.state_dict(), "metrics": metrics,
                        "ffba_advances": ffba_advances}, ckpt)

    final = f"{OUT_DIR}/ppo_{label}_final.pt"
    torch.save({"model": agent.net.state_dict(), "metrics": metrics,
                "ffba_advances": ffba_advances}, final)
    with open(final.replace(".pt", "_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nFinal: {final}", flush=True)
    print(f"FFBA advances: {ffba_advances} / {len(completed_returns)} eps", flush=True)
    cmd_q.put("close")
    worker.join(timeout=5)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    label = sys.argv[3] if len(sys.argv) > 3 else "shalamar_sp"
    main(epochs=epochs, steps_per_epoch=steps, label=label)
