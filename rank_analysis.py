#!/usr/bin/env python3
"""
rank_analysis.py -- does replacing real programs by generator programs reorder models?

Input : rank_models.json (see PREREG_ranking.md) and the rerun_*.jsonl files written by
        `cafa_revision.py rerun --conditions 1,2` (one file per model and prompt).
Output: for each prompt, a table (accuracy and rank on real and on generator programs), Kendall's tau-b
        between the two rankings with a program-level bootstrap interval, the share of model pairs whose
        order flips (all pairs, and pairs that are decisive on real programs), and a split-half noise
        ceiling for tau (real programs against real programs).

Only needs numpy (matplotlib optional, for the rank-against-rank chart).
Usage:  python3 rank_analysis.py rank_models.json [--boot 10000] [--splits 1000] [--seed 20261012] [--out rank_out]
"""
import argparse
import csv
import json
import os
import sys

import numpy as np


def load_correct(path):
    """{(sample_index, condition_id): 0/1} for scored cells (status ok); later records win."""
    d = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("status") == "ok":
                d[(r["sample_index"], r["condition_id"])] = int(bool(r["correct"]))
    return d


def average_ranks(x):
    """rank 1 = highest value; ties share the mean rank."""
    order = np.argsort(-x, kind="mergesort")
    ranks = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def tau_b(X, Y, iu, ju):
    """Kendall tau-b between columns of X and Y (m x B each), vectorised over B."""
    dx = np.sign(X[iu] - X[ju])
    dy = np.sign(Y[iu] - Y[ju])
    P = dx.shape[0]
    num = (dx * dy).sum(axis=0)
    n1 = (dx == 0).sum(axis=0)
    n2 = (dy == 0).sum(axis=0)
    den = np.sqrt((P - n1).astype(float) * (P - n2).astype(float))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def flip_share(X, Y, iu, ju):
    dx = np.sign(X[iu] - X[ju])
    dy = np.sign(Y[iu] - Y[ju])
    return (dx * dy < 0).mean(axis=0)


def analyse(R, S, names, boot, splits, rng):
    """R, S: m x N 0/1 matrices (real and generator programs, same N programs, same order)."""
    m, N = R.shape
    iu, ju = np.triu_indices(m, 1)
    accR, accS = R.sum(1) / N, S.sum(1) / N
    res = {"m": m, "N": N, "pairs": int(len(iu))}
    res["tau"] = float(tau_b(accR[:, None], accS[:, None], iu, ju)[0])
    res["flip_share"] = float(flip_share(accR[:, None], accS[:, None], iu, ju)[0])
    res["tie_share_real"] = float((accR[iu] == accR[ju]).mean())
    res["tie_share_synth"] = float((accS[iu] == accS[ju]).mean())
    # program-level bootstrap: the same resampled programs are used for real and generator accuracies
    taus, flips, bR, bS = [], [], [], []
    done = 0
    while done < boot:
        b = min(1000, boot - done)
        W = rng.multinomial(N, np.full(N, 1.0 / N), size=b).T.astype(np.int64)   # N x b
        cR, cS = (R @ W).astype(float), (S @ W).astype(float)                     # m x b, exact counts
        taus.append(tau_b(cR, cS, iu, ju)); flips.append(flip_share(cR, cS, iu, ju))
        bR.append(cR / N); bS.append(cS / N)
        done += b
    taus, flips = np.concatenate(taus), np.concatenate(flips)
    bR = np.concatenate(bR, axis=1)
    res["tau_ci"] = [float(np.nanpercentile(taus, 2.5)), float(np.nanpercentile(taus, 97.5))]
    res["flip_ci"] = [float(np.percentile(flips, 2.5)), float(np.percentile(flips, 97.5))]
    # pairs whose order on real programs is itself resolved (bootstrap interval of the difference excludes 0)
    d = bR[iu] - bR[ju]
    lo, hi = np.percentile(d, 2.5, axis=1), np.percentile(d, 97.5, axis=1)
    dec = (lo > 0) | (hi < 0)
    res["decisive_pairs"] = int(dec.sum())
    dx, dy = np.sign(accR[iu] - accR[ju]), np.sign(accS[iu] - accS[ju])
    res["decisive_flips"] = int(((dx * dy < 0) & dec).sum())
    res["decisive_flip_share"] = float(res["decisive_flips"] / dec.sum()) if dec.sum() else None
    # noise ceiling: tau between two random disjoint halves of the REAL programs (and of the generator programs)
    sh_r, sh_s = [], []
    h = N // 2
    for _ in range(splits):
        p = rng.permutation(N); A, B = p[:h], p[h:2 * h]
        sh_r.append(tau_b(R[:, A].sum(1)[:, None] / h, R[:, B].sum(1)[:, None] / h, iu, ju)[0])
        sh_s.append(tau_b(S[:, A].sum(1)[:, None] / h, S[:, B].sum(1)[:, None] / h, iu, ju)[0])
    sh_r, sh_s = np.array(sh_r), np.array(sh_s)
    res["split_half_real"] = {"median": float(np.nanmedian(sh_r)), "p05": float(np.nanpercentile(sh_r, 5))}
    res["split_half_synth"] = {"median": float(np.nanmedian(sh_s)), "p05": float(np.nanpercentile(sh_s, 5))}
    res["material_rule"] = "tau below the 5th percentile of the real-vs-real split-half tau"
    res["material"] = bool(res["tau"] < res["split_half_real"]["p05"])
    return res, accR, accS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--splits", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--out", default="rank_out")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    rc, sc = cfg.get("real_cond", 1), cfg.get("synth_cond", 2)
    prompts = cfg.get("prompts", ["orig", "none"])
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    summary = {"config": a.config, "seed": a.seed, "boot": a.boot, "splits": a.splits, "prompts": {}}
    for pr in prompts:
        models = [m for m in cfg["models"] if pr in m.get("files", {})]
        data, missing = {}, []
        for m in models:
            p = m["files"][pr]
            if not os.path.exists(p):
                missing.append(m["name"]); continue
            data[m["name"]] = load_correct(p)
        if missing:
            print(f"[{pr}] files missing for: {', '.join(missing)}", file=sys.stderr)
        names = [m["name"] for m in models if m["name"] in data]
        if len(names) < 3:
            print(f"[{pr}] fewer than three models with results; skipped"); continue
        # programs scored for every model in both conditions
        common = None
        for n in names:
            ok = {s for (s, c) in data[n] if c == rc and (s, sc) in data[n]}
            common = ok if common is None else common & ok
        progs = sorted(common)
        print(f"\n=== prompt: {pr}   models: {len(names)}   programs scored for every model in both conditions: {len(progs)}")
        R = np.array([[data[n][(s, rc)] for s in progs] for n in names], dtype=np.int64)
        S = np.array([[data[n][(s, sc)] for s in progs] for n in names], dtype=np.int64)
        res, accR, accS = analyse(R, S, names, a.boot, a.splits, rng)
        rkR, rkS = average_ranks(accR), average_ranks(accS)
        res["models"] = names
        info = {m["name"]: m for m in models}
        rows = [(n, info[n].get("params_b", ""), accR[i], accS[i], rkR[i], rkS[i]) for i, n in enumerate(names)]
        rows.sort(key=lambda r: r[4])
        with open(os.path.join(a.out, f"rank_table_{pr}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["model", "params_b", "acc_real", "acc_generator", "rank_real", "rank_generator"])
            for r in rows: w.writerow([r[0], r[1], f"{r[2]:.4f}", f"{r[3]:.4f}", f"{r[4]:g}", f"{r[5]:g}"])
        print(f"{'model':28s} {'B':>5s} {'real':>7s} {'gen.':>7s} {'rk real':>8s} {'rk gen.':>8s}")
        for r in rows:
            print(f"{r[0]:28s} {str(r[1]):>5s} {100*r[2]:7.1f} {100*r[3]:7.1f} {r[4]:8g} {r[5]:8g}")
        print(f"Kendall tau-b = {res['tau']:.3f}  95% CI [{res['tau_ci'][0]:.3f}, {res['tau_ci'][1]:.3f}]")
        print(f"pairs with a different order: {100*res['flip_share']:.1f}% of {res['pairs']}  "
              f"[{100*res['flip_ci'][0]:.1f}, {100*res['flip_ci'][1]:.1f}]; "
              f"among {res['decisive_pairs']} pairs resolved on real programs: {res['decisive_flips']} flip "
              f"({100*res['decisive_flip_share']:.1f}%)" if res['decisive_pairs'] else "no resolved pairs")
        print(f"noise ceiling (real vs real, split halves): median tau {res['split_half_real']['median']:.3f}, "
              f"5th percentile {res['split_half_real']['p05']:.3f}")
        print(f"pre-registered rule -> reordering material: {res['material']}")
        summary["prompts"][pr] = res
        try:
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.scatter(rkR, rkS, s=18)
            for i, n in enumerate(names): ax.annotate(n, (rkR[i], rkS[i]), fontsize=6, xytext=(3, 2), textcoords="offset points")
            lim = [0.5, len(names) + 0.5]; ax.plot(lim, lim, lw=0.8, color="grey"); ax.set_xlim(lim); ax.set_ylim(lim)
            ax.set_xlabel("rank on real programs"); ax.set_ylabel("rank on generator programs"); ax.set_title(f"prompt: {pr}   tau = {res['tau']:.2f}")
            fig.tight_layout(); fig.savefig(os.path.join(a.out, f"rank_vs_rank_{pr}.png"), dpi=200); plt.close(fig)
        except Exception as e:
            print("chart skipped:", type(e).__name__)
    json.dump(summary, open(os.path.join(a.out, "rank_summary.json"), "w"), indent=1)
    print(f"\nwrote {a.out}/rank_summary.json")


if __name__ == "__main__":
    main()
