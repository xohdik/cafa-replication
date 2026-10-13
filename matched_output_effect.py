#!/usr/bin/env python3
"""
matched_output_effect.py -- the syntheticity effect WITHIN output-shape strata (paired by program).

Each sample has a real program (C1) and a matched synthetic program (C2). The pooled syntheticity effect
mixes a composition difference: real programs include many multi-line outputs (hard), synthetic ones
none. Here programs are split by the shape of the REAL program's expected output and the SYNTHETIC
program's expected output (from the manifest, executed like the harness), and the same signed
syntheticity effect as Table VII is computed inside each group:
    effect = mean over the 4 synthetic conditions - mean over the 4 real conditions   (per program)
Groups:
  ALL                       : every program (reproduces Table VII's syntheticity row)
  real single & synth single: like-for-like output shape (the cleanest comparison)
  real multi                : real output has several lines; synthetic output is single-line or zero
Program-level bootstrap CIs; the model difference uses the same resamples.

Usage: python3 -W ignore matched_output_effect.py --manifest manifest.json \
          responses_deepseek.json:DeepSeek responses_qwen.json:Qwen
Requires output_strata.py and paired_effects.py in the same directory.
"""
import argparse
import numpy as np
from paired_effects import load, effect_vec, SYNTH, REAL
from output_strata import expected_strata


def boot_idx(n, B, rng):
    return rng.integers(0, n, (B, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    models = []
    for spec in a.specs:
        path, _, label = spec.partition(":")
        pids, A = load(path)
        models.append((label or path, pids, A.mean(2)))
    pids = models[0][1]
    assert all(m[1] == pids for m in models), "program ids differ"
    S = expected_strata(a.manifest, pids)
    groups = {
        "ALL programs": np.ones(len(pids), bool),
        "real single & synth single": (S[1] == "single") & (S[2] == "single"),
        "real multi-line": S[1] == "multi",
        "synth zero (real single)": (S[1] == "single") & (S[2] == "zero"),
    }
    vecs = {lab: effect_vec(P, SYNTH, REAL) for lab, _, P in models}

    def ci(v, idx):
        b = v[idx].mean(1)
        lo, hi = np.percentile(b, [2.5, 97.5])
        p = max(2 * min((b <= 0).mean(), (b >= 0).mean()), 1.0 / (len(b) + 1))
        return v.mean(), lo, hi, p

    print(f"{'group':<30}{'n':>5}   " + "   ".join(f"{lab:<30}" for lab, _, _ in models) +
          ("   model diff (first - second)" if len(models) == 2 else ""))
    for g, mk in groups.items():
        n = int(mk.sum())
        if n < 20:
            print(f"{g:<30}{n:>5}   too few programs")
            continue
        idx = boot_idx(n, a.boot, rng)
        cells = []
        sub = {}
        for lab, _, _ in models:
            v = vecs[lab][mk]
            sub[lab] = v
            m, lo, hi, p = ci(v, idx)
            cells.append(f"{m:+.3f} [{lo:+.3f},{hi:+.3f}] p={p:.3g}".ljust(30))
        line = f"{g:<30}{n:>5}   " + "   ".join(cells)
        if len(models) == 2:
            d = sub[models[0][0]] - sub[models[1][0]]
            m, lo, hi, p = ci(d, idx)
            line += f"   {m:+.3f} [{lo:+.3f},{hi:+.3f}] p={p:.3g}"
        print(line)
    print("\nEffects are signed accuracy differences (synthetic minus real); negative = synthetic is harder.")
    print("Groups are exploratory subsets defined from program outputs in the manifest, not from model scores.")


if __name__ == "__main__":
    main()
