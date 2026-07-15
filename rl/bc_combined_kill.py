"""BC train on combined kill datasets: v19 mini-boss synth + Shalamar oracle.

Warm-starts from bc_kill_oversampled (mini-boss-capable) and adds Shalamar demos.
"""
from __future__ import annotations
import os, sys, time, json
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
torch.set_num_threads(1)

sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from penta_rl.ppo import PolicyValueNet, PPOConfig
from penta_rl.state import vector_dim
from penta_rl.env import N_ACTIONS

NPZ_V19 = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data/expert_v19_synth_kills.npz"
NPZ_SHALAMAR = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data/expert_shalamar_oracle.npz"
WARM_START = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_kill_oversampled.pt"
OUT_PATH = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_combined_kill.pt"

KILL_WINDOW = 50
KILL_BOOST = 10.0
EPOCHS = 20  # fewer — we observed overfit after ~8 last time
BATCH_SIZE = 256
LR = 2e-4
VAL_FRAC = 0.1


def build_sample_weights(kill_mask, src):
    weights = np.ones(len(kill_mask), dtype=np.float32)
    kill_idx = np.where(kill_mask > 0)[0]
    for ki in kill_idx:
        ki_src = src[ki]
        for j in range(KILL_WINDOW):
            i = ki - j
            if i < 0 or src[i] != ki_src: break
            weights[i] = max(weights[i], KILL_BOOST)
        for j in range(KILL_WINDOW):
            i = ki + j
            if i >= len(src) or src[i] != ki_src: break
            weights[i] = max(weights[i], KILL_BOOST)
    return weights


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    obs_dim = vector_dim()

    parts = []
    for path, tag in [(NPZ_V19, "v19"), (NPZ_SHALAMAR, "shalamar")]:
        d = np.load(path, allow_pickle=True)
        n = len(d["X"])
        parts.append({"X": d["X"], "y": d["y"], "kill_mask": d["kill_mask"], "src": d["src"]})
        print(f"  {tag}: {n} samples, {int(d['kill_mask'].sum())} kill events")

    X = np.concatenate([p["X"] for p in parts])
    y = np.concatenate([p["y"] for p in parts])
    kill_mask = np.concatenate([p["kill_mask"] for p in parts])
    src = np.concatenate([p["src"] for p in parts])
    print(f"Combined: {len(X)} samples, {int(kill_mask.sum())} kills")

    weights_full = build_sample_weights(kill_mask, src)
    print(f"Kill-window frames: {int((weights_full > 1.0).sum())}")

    rng = np.random.default_rng(20260510)
    perm = rng.permutation(len(X))
    X = X[perm]; y = y[perm]; weights_full = weights_full[perm]

    n_val = int(len(X) * VAL_FRAC)
    Xt, yt, wt = X[n_val:], y[n_val:], weights_full[n_val:]
    Xv, yv, wv = X[:n_val], y[:n_val], weights_full[:n_val]

    cfg = PPOConfig()
    net = PolicyValueNet(obs_dim, N_ACTIONS, cfg.hidden).to(device)
    if os.path.exists(WARM_START):
        warm = torch.load(WARM_START, map_location=device, weights_only=False)
        net.load_state_dict(warm["model"])
        print(f"Warm-started from {WARM_START}")
    opt = optim.Adam(net.parameters(), lr=LR)

    counts = np.bincount(yt, minlength=N_ACTIONS).astype(np.float32)
    counts = np.maximum(counts, 1.0)
    cls_w = torch.as_tensor(counts.sum() / (N_ACTIONS * counts), dtype=torch.float32, device=device)

    Xt_t = torch.as_tensor(Xt, dtype=torch.float32, device=device)
    yt_t = torch.as_tensor(yt, dtype=torch.long, device=device)
    wt_t = torch.as_tensor(wt, dtype=torch.float32, device=device)
    Xv_t = torch.as_tensor(Xv, dtype=torch.float32, device=device)
    yv_t = torch.as_tensor(yv, dtype=torch.long, device=device)
    wv_t = torch.as_tensor(wv, dtype=torch.float32, device=device)

    history = []
    best_kill_acc = -1.0
    best_path = OUT_PATH.replace(".pt", "_best.pt")
    t0 = time.time()
    for ep in range(EPOCHS):
        net.train()
        idx = torch.randperm(len(Xt_t), device=device)
        loss_sum, c, n = 0.0, 0, 0
        kc, kn = 0, 0
        for s in range(0, len(idx), BATCH_SIZE):
            j = idx[s:s+BATCH_SIZE]
            xb, yb, wb = Xt_t[j], yt_t[j], wt_t[j]
            logits, _ = net(xb)
            loss = (nn.functional.cross_entropy(logits, yb, weight=cls_w, reduction="none") * wb).mean()
            opt.zero_grad(); loss.backward(); opt.step()
            loss_sum += loss.item() * len(yb)
            pred = logits.argmax(-1)
            c += (pred == yb).sum().item(); n += len(yb)
            km = wb > 1.0
            if km.any():
                kc += (pred[km] == yb[km]).sum().item(); kn += int(km.sum().item())
        net.eval()
        with torch.no_grad():
            vlogits, _ = net(Xv_t)
            vloss = nn.functional.cross_entropy(vlogits, yv_t, weight=cls_w).item()
            vpred = vlogits.argmax(-1)
            vacc = (vpred == yv_t).float().mean().item()
            vkm = wv_t > 1.0
            vkacc = ((vpred[vkm] == yv_t[vkm]).float().mean().item() if vkm.any() else 0.0)
        history.append({"epoch": ep+1, "train_loss": loss_sum/n, "train_acc": c/n,
                        "kill_train_acc": kc/max(kn,1), "val_loss": vloss, "val_acc": vacc,
                        "kill_val_acc": vkacc, "t": time.time()-t0})
        marker = ""
        if vkacc > best_kill_acc:
            best_kill_acc = vkacc
            torch.save({"model": net.state_dict(), "epoch": ep+1, "best_kill_acc": vkacc,
                        "history": history}, best_path)
            marker = " *BEST*"
        print(f"ep {ep+1:2d}/{EPOCHS}  loss={loss_sum/n:.4f}  acc={c/n:.3f}  "
              f"kill_acc={kc/max(kn,1):.3f}  v_loss={vloss:.4f}  v_acc={vacc:.3f}  "
              f"v_kill_acc={vkacc:.3f}{marker}")

    torch.save({"model": net.state_dict(), "history": history,
                "best_kill_acc": best_kill_acc}, OUT_PATH)
    print(f"\nSaved final: {OUT_PATH}")
    print(f"Saved best (epoch {history[np.argmax([h['kill_val_acc'] for h in history])]['epoch']}): {best_path}")


if __name__ == "__main__":
    main()
