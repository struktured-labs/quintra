"""BC train with kill-frame oversampling.

Loads expert_v19_synth_kills.npz, weights samples within ±KILL_WINDOW frames of
a kill_event 10× higher than non-combat frames. Trains PolicyValueNet from a
warm-start (existing bc_pretrained.pt) so we don't lose general navigation skill.
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

NPZ_PATH = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_data/expert_v19_synth_kills.npz"
WARM_START = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_pretrained.pt"
OUT_PATH = "/home/struktured/projects/penta-dragon-dx-claude/rl/bc_kill_oversampled.pt"

KILL_WINDOW = 50         # frames before+after a kill to upweight
KILL_BOOST = 10.0        # weight multiplier for kill-window frames
EPOCHS = 30
BATCH_SIZE = 256
LR = 3e-4
VAL_FRAC = 0.1


def build_sample_weights(kill_mask: np.ndarray, src: np.ndarray) -> np.ndarray:
    """Per-sample weights: KILL_BOOST for frames within ±KILL_WINDOW of any kill,
    1.0 otherwise. Kill windows do NOT cross episode/source boundaries."""
    weights = np.ones(len(kill_mask), dtype=np.float32)
    kill_idx = np.where(kill_mask > 0)[0]
    for ki in kill_idx:
        ki_src = src[ki]
        # Walk forward and backward respecting source boundary
        lo = ki
        for j in range(KILL_WINDOW):
            i = ki - j
            if i < 0 or src[i] != ki_src: break
            lo = i
        hi = ki
        for j in range(KILL_WINDOW):
            i = ki + j
            if i >= len(src) or src[i] != ki_src: break
            hi = i
        weights[lo:hi+1] = np.maximum(weights[lo:hi+1], KILL_BOOST)
    return weights


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}", flush=True)
    obs_dim = vector_dim()
    print(f"obs_dim = {obs_dim}", flush=True)

    data = np.load(NPZ_PATH, allow_pickle=True)
    X = data["X"]
    y = data["y"]
    kill_mask = data["kill_mask"]
    src = data["src"]
    print(f"Loaded {len(X)} samples, {kill_mask.sum()} kill events", flush=True)
    assert X.shape[1] == obs_dim, f"obs_dim mismatch: {X.shape[1]} vs {obs_dim}"

    weights_full = build_sample_weights(kill_mask, src)
    print(f"Sample weights: total={weights_full.sum():.0f}  "
          f"kill-window frames={int((weights_full > 1.0).sum())}", flush=True)

    n = len(X)
    rng = np.random.default_rng(42)
    perm = rng.permutation(n)
    X = X[perm]; y = y[perm]; weights_full = weights_full[perm]

    n_val = int(n * VAL_FRAC)
    X_train, y_train, w_train = X[n_val:], y[n_val:], weights_full[n_val:]
    X_val, y_val, w_val = X[:n_val], y[:n_val], weights_full[:n_val]
    print(f"Train: {len(X_train)}  Val: {len(X_val)}", flush=True)

    cfg = PPOConfig()
    net = PolicyValueNet(obs_dim, N_ACTIONS, cfg.hidden).to(device)
    if os.path.exists(WARM_START):
        warm = torch.load(WARM_START, map_location=device, weights_only=False)
        if "model" in warm:
            net.load_state_dict(warm["model"])
            print(f"Warm-started from {WARM_START}", flush=True)
        else:
            print(f"Warm-start file has no 'model' key, training from scratch", flush=True)
    opt = optim.Adam(net.parameters(), lr=LR)

    counts = np.bincount(y_train, minlength=N_ACTIONS).astype(np.float32)
    counts = np.maximum(counts, 1.0)
    cls_weights = (counts.sum() / (N_ACTIONS * counts))
    cls_weights = torch.as_tensor(cls_weights, dtype=torch.float32, device=device)
    print(f"Class weights: {cls_weights.cpu().numpy().round(2)}", flush=True)

    Xt = torch.as_tensor(X_train, dtype=torch.float32, device=device)
    yt = torch.as_tensor(y_train, dtype=torch.long, device=device)
    wt = torch.as_tensor(w_train, dtype=torch.float32, device=device)
    Xv = torch.as_tensor(X_val, dtype=torch.float32, device=device)
    yv = torch.as_tensor(y_val, dtype=torch.long, device=device)
    wv = torch.as_tensor(w_val, dtype=torch.float32, device=device)

    history = []
    t0 = time.time()
    for ep in range(EPOCHS):
        net.train()
        idx = torch.randperm(len(Xt), device=device)
        ep_loss, n_correct, n_total, n_kill_correct, n_kill_total = 0.0, 0, 0, 0, 0
        for start in range(0, len(idx), BATCH_SIZE):
            j = idx[start:start+BATCH_SIZE]
            xb, yb, wb = Xt[j], yt[j], wt[j]
            logits, _ = net(xb)
            cls_logp = nn.functional.cross_entropy(
                logits, yb, weight=cls_weights, reduction="none")
            loss = (cls_logp * wb).mean()
            opt.zero_grad(); loss.backward(); opt.step()
            ep_loss += loss.item() * len(yb)
            preds = logits.argmax(-1)
            n_correct += (preds == yb).sum().item()
            n_total += len(yb)
            kill_in_batch = wb > 1.0
            if kill_in_batch.any():
                n_kill_correct += (preds[kill_in_batch] == yb[kill_in_batch]).sum().item()
                n_kill_total += int(kill_in_batch.sum().item())
        train_loss = ep_loss / n_total
        train_acc = n_correct / n_total
        kill_acc = n_kill_correct / max(n_kill_total, 1)

        net.eval()
        with torch.no_grad():
            vlogits, _ = net(Xv)
            vloss = nn.functional.cross_entropy(vlogits, yv, weight=cls_weights).item()
            vpred = vlogits.argmax(-1)
            vacc = (vpred == yv).float().mean().item()
            kill_in_val = wv > 1.0
            vkill_acc = ((vpred[kill_in_val] == yv[kill_in_val]).float().mean().item()
                         if kill_in_val.any() else 0.0)
        elapsed = time.time() - t0
        history.append({"epoch": ep+1, "train_loss": train_loss, "train_acc": train_acc,
                        "kill_train_acc": kill_acc, "val_loss": vloss, "val_acc": vacc,
                        "kill_val_acc": vkill_acc, "elapsed_s": elapsed})
        print(f"ep {ep+1:2d}/{EPOCHS}  loss={train_loss:.4f}  acc={train_acc:.3f}  "
              f"kill_acc={kill_acc:.3f}  v_loss={vloss:.4f}  v_acc={vacc:.3f}  "
              f"v_kill_acc={vkill_acc:.3f}  t={elapsed:.0f}s", flush=True)

    torch.save({"model": net.state_dict(), "history": history,
                "kill_window": KILL_WINDOW, "kill_boost": KILL_BOOST,
                "n_kill_events": int(kill_mask.sum()),
                "warm_start": WARM_START if os.path.exists(WARM_START) else None}, OUT_PATH)
    with open(OUT_PATH.replace(".pt", "_history.json"), "w") as f:
        json.dump(history, f, indent=2)
    print(f"\nSaved {OUT_PATH}", flush=True)
    return OUT_PATH


if __name__ == "__main__":
    main()
