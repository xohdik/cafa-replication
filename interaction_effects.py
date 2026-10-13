#!/usr/bin/env python3
"""
interaction_effects.py -- SIGNED effects for all 7 terms of the 2^3 design, with
program-level bootstrap CIs, Holm-adjusted p-values, and paired model differences.

Terms: identifiers (I), ast_structure (A), syntheticity (S), I*A, I*S, A*S, I*A*S.
Coding: +1 = perturbed level (Obf / Shuf / Synth), -1 = baseline (Orig / Orig / Real).

Reported quantities are in accuracy points and are directly interpretable:
  main effect        = mean(perturbed conditions) - mean(baseline conditions)
  2-way interaction  = difference-in-differences: effect of X when Y is perturbed
                       minus effect of X when Y is baseline   (averaged over the 3rd factor)
  3-way interaction  = difference of that difference between the two levels of the 3rd factor
Sign of a 2-way term: negative = the two perturbations together hurt MORE than the sum of
their separate effects (synergy); positive = they overlap (hurt less than the sum).

Inference: programs are resampled (same resampled indices for every term and every model),
because the 3 greedy reps are near-duplicates. p = two-sided bootstrap p, floor 1/(B+1);
Holm step-down across the 7 terms within each model. Paired model differences use the same
resamples.

Usage:
    python3 interaction_effects.py responses_deepseek.json:DeepSeek responses_qwen.json:Qwen
Requires paired_effects.py in the same directory.
"""
import argparse
import numpy as np
from paired_effects import load

ID = np.array([-1, -1, -1, -1, 1, 1, 1, 1], float)
AST = np.array([-1, -1, 1, 1, -1, -1, 1, 1], float)
SYN = np.array([-1, 1, -1, 1, -1, 1, -1, 1], float)

TERMS = {
    "identifiers (I)": (ID, 4),
    "ast_structure (A)": (AST, 4),
    "syntheticity (S)": (SYN, 4),
    "I x A": (ID * AST, 2),
    "I x S": (ID * SYN, 2),
    "A x S": (AST * SYN, 2),
    "I x A x S": (ID * AST * SYN, 1),
}


def contrast_vec(P, sign, div):
    """Per-program signed effect for one term. P: [programs, 8]."""
    return (P * sign).sum(1) / div


def boot_p(b):
    B = len(b)
    p = min(1.0, 2 * min((b <= 0).mean(), (b >= 0).mean()))
    return max(p, 1.0 / (B + 1))


def holm(ps):
    order = np.argsort(ps)
    m = len(ps)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="path:label (one or two)")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    models = []
    for s in a.specs:
        path, _, label = s.partition(":")
        pids, A = load(path)
        models.append((label or path, pids, A.mean(2)))
    if len(models) == 2 and models[0][1] != models[1][1]:
        raise SystemExit("Program ids differ between the two files; cannot pair.")

    n = len(models[0][1])
    rng = np.random.default_rng(a.seed)
    idx = rng.integers(0, n, (a.boot, n))
    print(f"programs={n}  bootstrap={a.boot} (resampling PROGRAMS)  seed={a.seed}")

    vecs = {}
    for label, _, P in models:
        print("\n" + "=" * 86)
        print(label)
        print("=" * 86)
        print(f"{'term':<20}{'effect':>9}   {'95% CI (programs)':<22}{'p':>9}{'Holm p':>9}")
        names, ps, rows = [], [], []
        for name, (sign, div) in TERMS.items():
            v = contrast_vec(P, sign, div)
            vecs[(label, name)] = v
            b = v[idx].mean(1)
            lo, hi = np.percentile(b, [2.5, 97.5])
            names.append(name)
            ps.append(boot_p(b))
            rows.append((v.mean(), lo, hi))
        adj = holm(np.array(ps))
        for nm, (m, lo, hi), p, pa in zip(names, rows, ps, adj):
            print(f"{nm:<20}{m:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]   {p:>9.4g}{pa:>8.4f}{stars(pa)}")

    if len(models) == 2:
        (la, _, _), (lb, _, _) = models
        print("\n" + "=" * 86)
        print(f"PAIRED MODEL DIFFERENCE ({la} - {lb}), same programs, same resamples")
        print("=" * 86)
        print(f"{'term':<20}{'diff':>9}   {'95% CI':<22}{'p':>9}{'Holm p':>9}")
        names, ps, rows = [], [], []
        for name in TERMS:
            dv = vecs[(la, name)] - vecs[(lb, name)]
            b = dv[idx].mean(1)
            lo, hi = np.percentile(b, [2.5, 97.5])
            names.append(name)
            ps.append(boot_p(b))
            rows.append((dv.mean(), lo, hi))
        adj = holm(np.array(ps))
        for nm, (m, lo, hi), p, pa in zip(names, rows, ps, adj):
            print(f"{nm:<20}{m:>+9.4f}   [{lo:+.4f}, {hi:+.4f}]   {p:>9.4g}{pa:>8.4f}{stars(pa)}")
    print("\n* p<.05  ** p<.01  *** p<.001 (Holm-adjusted within each table)")


if __name__ == "__main__":
    main()
