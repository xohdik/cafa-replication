#!/usr/bin/env python3
"""
paired_effects.py -- signed main effects with program-level (paired) bootstrap.

Reads per_sample_results from one or two responses files:
    per_sample_results[program_id][condition_id] = [rep1, rep2, rep3]  (0/1)

Condition coding:
    C1 (Orig,Orig,Real)  C2 (Orig,Orig,Synth)
    C3 (Orig,Shuf,Real)  C4 (Orig,Shuf,Synth)
    C5 (Obf, Orig,Real)  C6 (Obf, Orig,Synth)
    C7 (Obf, Shuf,Real)  C8 (Obf, Shuf,Synth)

Signs: every effect is (perturbed level) - (baseline level), so
    syntheticity  > 0  means synthetic programs are EASIER than real ones
    identifiers   < 0  means obfuscation HURTS
    ast_structure < 0  means shuffling HURTS

Usage:
    python3 paired_effects.py responses.json:DeepSeek responses_qwen.json:Qwen
    python3 paired_effects.py responses_qwen.json:Qwen          (single model)
"""
import argparse
import json
import math

import numpy as np

REAL, SYNTH = [1, 3, 5, 7], [2, 4, 6, 8]
ORIG_ID, OBF = [1, 2, 3, 4], [5, 6, 7, 8]
ORIG_AST, SHUF = [1, 2, 5, 6], [3, 4, 7, 8]
PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8)]  # (real, synth), other factors fixed

FACTORS = {
    "syntheticity": (SYNTH, REAL),
    "identifiers": (OBF, ORIG_ID),
    "ast_structure": (SHUF, ORIG_AST),
}


def load(path):
    d = json.load(open(path))
    p = d["per_sample_results"]
    pids = sorted(p, key=lambda k: int(k))
    reps = min(len(p[pid][str(c)]) for pid in pids for c in range(1, 9))
    A = np.array(
        [[p[pid][str(c)][:reps] for c in range(1, 9)] for pid in pids], dtype=float
    )  # [programs, 8 conditions, reps]
    return pids, A


def effect_vec(P, hi, lo):
    """Per-program signed effect: mean over `hi` conditions minus mean over `lo`."""
    return P[:, [c - 1 for c in hi]].mean(1) - P[:, [c - 1 for c in lo]].mean(1)


def boot_mean(vec, idx):
    return vec[idx].mean(1)


def ci(x):
    return np.percentile(x, [2.5, 97.5])


def sign_test_p(b, c):
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2.0 * tail / (2 ** n))


def rep_only_ci(A, hi, lo, rng, B):
    """CI when ONLY reps are resampled and programs are held fixed (for comparison)."""
    n, _, R = A.shape
    out = np.empty(B)
    for b in range(B):
        r = rng.integers(0, R, R)
        P = A[:, :, r].mean(2)
        out[b] = effect_vec(P, hi, lo).mean()
    return ci(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="path:label (one or two)")
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    models = []
    for s in a.specs:
        path, _, label = s.partition(":")
        pids, A = load(path)
        models.append((label or path, pids, A))
    if len(models) == 2 and models[0][1] != models[1][1]:
        raise SystemExit("Program ids differ between the two files; cannot pair.")

    n = len(models[0][1])
    rng = np.random.default_rng(a.seed)
    idx = rng.integers(0, n, (a.boot, n))  # SAME resampled programs for every model/effect

    print(f"programs={n}  bootstrap={a.boot} (resampling PROGRAMS)  seed={a.seed}")

    vecs = {}
    for label, _, A in models:
        P = A.mean(2)
        R = A.shape[2]
        print("\n" + "=" * 78)
        print(f"{label}   ({R} reps)")
        print("=" * 78)

        varying = (A.min(2) != A.max(2)).mean()
        print(f"cells (program x condition) whose reps are NOT all identical: {varying:.2%}")

        print("\nSIGNED MAIN EFFECTS (accuracy points, 95% CI)")
        print(f"{'factor':<15}{'effect':>9}   {'program-level CI':<22}{'rep-only CI':<22}")
        for name, (hi, lo) in FACTORS.items():
            v = effect_vec(P, hi, lo)
            vecs[(label, name)] = v
            m = v.mean()
            lo_ci, hi_ci = ci(boot_mean(v, idx))
            r_lo, r_hi = rep_only_ci(A, hi, lo, rng, 1000)
            print(
                f"{name:<15}{m:>+9.4f}   [{lo_ci:+.4f}, {hi_ci:+.4f}]   [{r_lo:+.4f}, {r_hi:+.4f}]"
            )

        print("\nMATCHED PAIRS: synthetic vs real, other factors fixed (majority-of-reps label)")
        print(f"{'pair':<10}{'real-only':>10}{'synth-only':>12}{'sign-test p':>14}{'delta acc':>12}")
        maj = A.sum(2) > (R / 2)
        for r_c, s_c in PAIRS:
            mr, ms = maj[:, r_c - 1], maj[:, s_c - 1]
            b = int((mr & ~ms).sum())   # real correct, synth wrong
            c = int((~mr & ms).sum())   # real wrong, synth correct
            d = P[:, s_c - 1].mean() - P[:, r_c - 1].mean()
            print(f"C{r_c}->C{s_c:<5}{b:>10}{c:>12}{sign_test_p(b, c):>14.4g}{d:>+12.4f}")

    if len(models) == 2:
        (la, _, _), (lb, _, _) = models
        print("\n" + "=" * 78)
        print(f"PAIRED DIFFERENCE IN SIGNED EFFECT: {la} - {lb}   (same programs, same resamples)")
        print("=" * 78)
        for name in FACTORS:
            dv = vecs[(la, name)] - vecs[(lb, name)]
            lo_ci, hi_ci = ci(boot_mean(dv, idx))
            sig = "SIGNIFICANT" if (lo_ci > 0 or hi_ci < 0) else "not significant"
            print(f"{name:<15}{dv.mean():>+9.4f}   [{lo_ci:+.4f}, {hi_ci:+.4f}]   {sig}")

        for label in (la, lb):
            v = vecs[(label, "syntheticity")]
            bs = boot_mean(v, idx)
            print(f"\nP(syntheticity effect > 0) for {label}: {(bs > 0).mean():.3f}")


if __name__ == "__main__":
    main()
