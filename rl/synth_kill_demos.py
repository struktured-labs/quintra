"""Generate synthetic mini-boss kill demos using v19 ep200 golden ckpt.

Rolls out v19 from saved states known to spawn mini-bosses (gargoyle, spider,
arena curriculum states), captures (state_vector, action, kill_event) per step,
and saves as .npz for direct BC consumption.

Also writes a JSONL audit log for inspection.
"""
from __future__ import annotations
import os, sys, time, json, glob, random
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import torch
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.env import N_ACTIONS, PentaEnv, ACTION_BUTTONS
from penta_rl.godmode_env import godmode_step
from penta_rl.state import vector_dim, read_state, state_to_vector
from penta_rl.ppo import PPOAgent, PPOConfig

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
V19_CKPT = "/home/struktured/projects/penta-dragon-dx-claude/rl/ppo_v19_resume18_ep200.pt"
OUT_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data"
OUT_JSONL = f"{OUT_DIR}/expert_v19_synth_kills.jsonl"
OUT_NPZ = f"{OUT_DIR}/expert_v19_synth_kills.npz"

# Rollout sources: stage-1 mini-boss arenas + curriculum starts where v19 reliably kills.
ROLLOUT_STATES = sorted(
    glob.glob("/home/struktured/projects/penta-dragon-dx-claude/rl/saves/gargoyle.state") +
    glob.glob("/home/struktured/projects/penta-dragon-dx-claude/rl/saves/cheat_gargoyle.state") +
    glob.glob("/home/struktured/projects/penta-dragon-dx-claude/rl/saves/spider.state") +
    glob.glob("/home/struktured/projects/penta-dragon-dx-claude/rl/saves/post_gargoyle_corridor.state") +
    glob.glob("/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum/arena_FFBA*.state")
)

EPISODES_PER_STATE = 12
MAX_EPISODE_STEPS = 1024


def load_agent(device="cpu"):
    obs_dim = vector_dim()
    cfg = PPOConfig(epochs=1, steps_per_epoch=1, train_iters=1, entropy_coef=0.01)
    agent = PPOAgent(obs_dim, N_ACTIONS, cfg, device=device)
    state = torch.load(V19_CKPT, map_location=device, weights_only=False)
    agent.net.load_state_dict(state["model"])
    agent.net.eval()
    return agent


def policy_logits_value(agent, obs):
    with torch.no_grad():
        x = torch.from_numpy(obs).float().unsqueeze(0)
        logits, v = agent.net(x)
    return logits.numpy().flatten(), float(v.item())


def serialize_record(env, f, action, keys_bitmask, kill_event):
    pb = env.pb
    s = read_state(pb)
    rec = {
        "f": f,
        "action": action,
        "keys": keys_bitmask,
        "D880": s.scene,
        "FFBA": s.level,
        "FFBD": s.room,
        "FFBE": pb.memory[0xFFBE],
        "FFBF": s.miniboss,
        "FFC0": pb.memory[0xFFC0],
        "FFC1": pb.memory[0xFFC1],
        "DCBB": s.boss_hp,
        "DCDC": pb.memory[0xDCDC],
        "DCDD": pb.memory[0xDCDD],
        "DCB8": pb.memory[0xDCB8],
        "FFAC": pb.memory[0xFFAC],
        "FFAD": pb.memory[0xFFAD],
        "FFCF": pb.memory[0xFFCF],
        "SCY": pb.memory[0xFF42],
        "SCX": pb.memory[0xFF43],
        "kill_event": kill_event,  # 0=none, 1=miniboss kill on this frame
    }
    return rec


def action_to_keys(action: int) -> int:
    """Re-derive the raw mgba keymask used by play_record.lua schema for parity."""
    buttons = ACTION_BUTTONS[action]
    bit = 0
    name_to_bit = {"a": 0x01, "b": 0x02, "select": 0x04, "start": 0x08,
                   "right": 0x10, "left": 0x20, "up": 0x40, "down": 0x80}
    for b in buttons:
        bit |= name_to_bit.get(getattr(b, "name", str(b)).lower(), 0)
    return bit


def rollout_state(agent, env, savestate_path, n_episodes, rng, fout, obs_buf, act_buf, kill_buf, src_buf):
    env.savestate_path = savestate_path
    label = os.path.basename(savestate_path).replace(".state", "")
    src_kills = 0
    src_steps = 0
    src_eps = 0
    for ep in range(n_episodes):
        obs, info = env.reset()
        prev_ffbf = info["state"].miniboss
        ep_kill_frames = []
        ep_records = []
        ep_obs = []
        ep_act = []
        ep_kill = []
        for step in range(MAX_EPISODE_STEPS):
            logits, _ = policy_logits_value(agent, obs)
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()
            a = int(rng.choice(N_ACTIONS, p=probs))
            obs2, r, term, trunc, info = env.step(a)
            cur_ffbf = info["state"].miniboss
            kill_event = 1 if (prev_ffbf != 0 and cur_ffbf == 0) else 0
            keys = action_to_keys(a)
            ep_records.append(serialize_record(env, step, a, keys, kill_event))
            ep_obs.append(obs.copy())
            ep_act.append(a)
            ep_kill.append(kill_event)
            if kill_event:
                ep_kill_frames.append(step)
                src_kills += 1
            prev_ffbf = cur_ffbf
            obs = obs2
            src_steps += 1
            if term or trunc:
                break
        # Only emit episodes that produced at least one kill OR a small fraction of misses.
        keep = bool(ep_kill_frames) or rng.random() < 0.2
        if keep:
            for rec in ep_records:
                rec["src"] = label
                rec["episode_idx"] = ep
                fout.write(json.dumps(rec) + "\n")
            obs_buf.extend(ep_obs)
            act_buf.extend(ep_act)
            kill_buf.extend(ep_kill)
            src_buf.extend([label] * len(ep_obs))
            src_eps += 1
        if ep_kill_frames:
            print(f"  [{label}] ep{ep}: KILLS at frames {ep_kill_frames}", flush=True)
    return {"label": label, "kills": src_kills, "steps": src_steps,
            "episodes_kept": src_eps, "episodes_total": n_episodes}


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Loading v19 ep200 from {V19_CKPT}", flush=True)
    agent = load_agent("cpu")
    print(f"Found {len(ROLLOUT_STATES)} rollout states", flush=True)
    rng = np.random.default_rng(20260509)
    env = PentaEnv(ROM, max_steps=MAX_EPISODE_STEPS,
                   savestate_path=ROLLOUT_STATES[0] if ROLLOUT_STATES else None)
    summaries = []
    obs_buf, act_buf, kill_buf, src_buf = [], [], [], []
    t0 = time.time()
    with open(OUT_JSONL, "w") as fout:
        for sp in ROLLOUT_STATES:
            print(f"\n=== Rolling {EPISODES_PER_STATE} episodes from {os.path.basename(sp)} ===", flush=True)
            try:
                summ = rollout_state(agent, env, sp, EPISODES_PER_STATE, rng, fout,
                                     obs_buf, act_buf, kill_buf, src_buf)
                summaries.append(summ)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
    env.close()
    elapsed = time.time() - t0
    print(f"\n=== DONE in {elapsed:.1f}s ===", flush=True)
    total_kills = sum(s["kills"] for s in summaries)
    total_eps_kept = sum(s["episodes_kept"] for s in summaries)
    print(f"Total kills captured: {total_kills} across {total_eps_kept} kept episodes")

    # Save numpy arrays for BC training
    if obs_buf:
        X = np.stack(obs_buf).astype(np.float32)
        y = np.asarray(act_buf, dtype=np.int64)
        kill_mask = np.asarray(kill_buf, dtype=np.int64)
        src_arr = np.asarray(src_buf)
        np.savez_compressed(OUT_NPZ, X=X, y=y, kill_mask=kill_mask, src=src_arr)
        print(f"Saved npz: {OUT_NPZ}  X.shape={X.shape}  kills_in_mask={kill_mask.sum()}")
    print(f"Saved jsonl: {OUT_JSONL}")
    for s in summaries:
        print(f"  {s['label']:<45}  kills={s['kills']:>3} kept_eps={s['episodes_kept']}/{s['episodes_total']} steps={s['steps']}")
