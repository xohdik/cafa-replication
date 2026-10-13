#!/usr/bin/env python3
"""
cafa_shares.py -- functional-ANOVA (Hoeffding) shares for the CAFA 2^3 design,
with PROGRAM-level bootstrap intervals.

Definition (exact for a full +-1 factorial):
    y_c   = mean accuracy of condition c over programs (8 values)
    term  = (mean_c  sign_S(c) * y_c)^2          for each subset S of factors
    share = term / Var_c(y_c)                   -> the 7 shares sum to 100%
    S_i   = share of {i}
    S_Ti  = sum of shares of every subset containing i   (exact, no aliasing)

The denominator is the BETWEEN-CONDITION variance of the response surface.
It says how the design-induced variation divides among factors; it does NOT
say whether any effect is statistically real (use paired_effects.py for that),
and it is unstable when that variance is tiny.

Requires paired_effects.py in the same directory (reuses its loader).

Usage:
    python3 cafa_shares.py responses_deepseek.json:DeepSeek responses_qwen.json:Qwen
"""
import argparse
import itertools

import numpy as np

from paired_effects import load

NAMES = ["identifiers", "ast_structure", "syntheticity"]
# condition id -> (identifiers, ast_structure, syntheticity), 0 = baseline level
CODE = {1: (0, 0, 0), 2: (0, 0, 1), 3: (0, 1, 0), 4: (0, 1, 1),
        5: (1, 0, 0), 6: (1, 0, 1), 7: (1, 1, 0), 8: (1, 1, 1)}
X = np.array([CODE[c] for c in range(1, 9)]) * 2 - 1  # +-1, shape (8, 3)
SUBSETS = [s for r in (1, 2, 3) for s in itertools.combinations(range(3), r)]
LABEL = {s: " x ".join(NAMES[i] for i in s) for s in SUBSETS}
SIGN = {s: np.prod(X[:, s], axis=1) for s in SUBSETS}


def shares(y):
    """y: (B, 8) cell means -> dict subset -> (B,) share in percent."""
    var = y.var(axis=1)
    var = np.where(var == 0, np.nan, var)
    return {s: 100.0 * ((y * SIGN[s]).mean(axis=1)) ** 2 / var for s in SUBSETS}


def totals(sh):
    S = {i: sh[(i,)] for i in range(3)}
    T = {i: sum(v for s, v in sh.items() if i in s) for i in range(3)}
    return S, T


def ci(x):
    return np.nanpercentile(x, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    models = []
    for s in a.specs:
        path, _, label = s.partition(":")
        pids, A = load(path)
        models.append((label or path, pids, A.mean(2)))  # (programs, 8) per-program accuracy
    if len(models) == 2 and models[0][1] != models[1][1]:
        raise SystemExit("Program ids differ between the two files; cannot pair.")

    n = len(models[0][1])
    rng = np.random.default_rng(a.seed)
    idx = rng.integers(0, n, (a.boot, n))  # same resampled programs for every model
    print(f"programs={n}  bootstrap={a.boot} (resampling PROGRAMS)  seed={a.seed}")

    store = {}
    for label, _, P in models:
        y0 = P.mean(0)[None, :]                      # (1, 8) point estimate
        yb = P[idx].mean(1)                          # (B, 8) bootstrap cell means
        sh0, shb = shares(y0), shares(yb)
        S0, T0 = totals(sh0)
        Sb, Tb = totals(shb)
        store[label] = (Sb, Tb)

        print("\n" + "=" * 78)
        print(label)
        print("=" * 78)
        print(f"between-condition SD of cell means: {y0.std():.4f}   "
              f"(95% CI {ci(yb.std(axis=1))[0]:.4f}-{ci(yb.std(axis=1))[1]:.4f})")
        print(f"\n{'term':<34}{'share %':>9}   {'program-level 95% CI':<24}")
        for s in SUBSETS:
            lo, hi = ci(shb[s])
            print(f"{LABEL[s]:<34}{sh0[s][0]:>9.2f}   [{lo:6.2f}, {hi:6.2f}]")
        print(f"{'(sum of all terms)':<34}{sum(v[0] for v in sh0.values()):>9.2f}")
        print(f"\n{'factor':<16}{'S_i %':>8}{'S_Ti %':>9}   {'S_Ti 95% CI':<20}")
        for i in range(3):
            lo, hi = ci(Tb[i])
            print(f"{NAMES[i]:<16}{S0[i][0]:>8.2f}{T0[i][0]:>9.2f}   [{lo:6.2f}, {hi:6.2f}]")

    if len(models) == 2:
        la, lb = models[0][0], models[1][0]
        print("\n" + "=" * 78)
        print(f"PAIRED DIFFERENCE IN S_i (percentage points): {la} - {lb}")
        print("=" * 78)
        Sa, _ = store[la]
        Sb_, _ = store[lb]
        for i in range(3):
            d = Sa[i] - Sb_[i]
            lo, hi = ci(d)
            sig = "SIGNIFICANT" if (lo > 0 or hi < 0) else "not significant"
            print(f"{NAMES[i]:<16}{np.nanmean(d):>+8.2f}   [{lo:+7.2f}, {hi:+7.2f}]   {sig}")


if __name__ == "__main__":
    main()
