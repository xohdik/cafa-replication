#!/usr/bin/env python3
"""
ast_subset_effects.py -- AST-shuffle effect restricted to programs the shuffle actually changed.

Why: only about half of the pool admits a shuffle (222/500 in x3_verification.json), and the
shuffles that happen are mild (median structural distance 0.018). For a program whose shuffled
source is IDENTICAL to the original, the AST contrast is zero by construction, so averaging over
all 480 programs dilutes any real effect by the unchanged fraction.

Eligibility (read from the manifest, per program): which of the four AST pairs
  (C1->C3), (C2->C4), (C5->C7), (C6->C8)
have source_code that differs between the baseline and the shuffled condition.
  PRIMARY subset  = the C1->C3 pair changed (shuffle altered the real, original-identifier program).
  ANY subset      = at least one of the four pairs changed.

Reports, per model: size of each subset, the signed AST effect (mean of the four pair differences)
on the subset with a program-level 95% bootstrap CI (resampling programs WITHIN the subset),
the effect on the unchanged complement (must be ~0: sanity check), the AST x syntheticity
difference-in-differences on the subset, and the C1->C3 pair alone.

Usage:
  python3 ast_subset_effects.py --manifest manifest.json responses_deepseek.json:DeepSeek responses_qwen.json:Qwen
Requires paired_effects.py in the same directory.
"""
import argparse
import ast
import json
import numpy as np
from paired_effects import load

PAIRS = [(1, 3), (2, 4), (5, 7), (6, 8)]          # (baseline AST, shuffled AST), other factors fixed


def same_program(a, b):
    """True if the two sources parse to the SAME syntax tree (same statements in the same order).
    Raw text cannot be compared: the unshuffled baseline C1 is the original text, while shuffled
    conditions went through an AST round-trip that rewrites formatting, comments and quotes."""
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return a == b


def changed_flags(manifest_path, pids):
    m = json.load(open(manifest_path))
    samples = m["samples"] if isinstance(m, dict) else m
    by_idx = {}
    for pos, s in enumerate(samples):
        src = {c["condition_id"]: c["source_code"] for c in s["conditions"]}
        flags = [int(not same_program(src[b], src[s_])) if (b in src and s_ in src) else 0 for b, s_ in PAIRS]
        by_idx[str(s.get("sample_index", pos))] = flags
    missing = [p for p in pids if p not in by_idx]
    if missing:
        raise SystemExit(f"{len(missing)} responses ids not found in manifest sample_index values (e.g. {missing[:5]}); "
                         "tell me how ids map to manifest rows.")
    return np.array([by_idx[p] for p in pids], dtype=bool)        # [programs, 4]


def ast_vec(P):
    """Per-program AST effect: mean over the four pairs of (shuffled - baseline)."""
    return np.mean([P[:, s - 1] - P[:, b - 1] for b, s in PAIRS], axis=0)


def ast_by_syn_dd(P):
    real = np.mean([P[:, 3 - 1] - P[:, 1 - 1], P[:, 7 - 1] - P[:, 5 - 1]], axis=0)
    syn = np.mean([P[:, 4 - 1] - P[:, 2 - 1], P[:, 8 - 1] - P[:, 6 - 1]], axis=0)
    return syn - real


def boot(v, rng, B):
    n = len(v)
    idx = rng.integers(0, n, (B, n))
    b = v[idx].mean(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    p = max(2 * min((b <= 0).mean(), (b >= 0).mean()), 1.0 / (B + 1))
    return v.mean(), lo, hi, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    for spec in a.specs:
        path, _, label = spec.partition(":")
        pids, A = load(path)
        P = A.mean(2)
        ch = changed_flags(a.manifest, pids)
        n = len(pids)
        subsets = {
            "PRIMARY (C1->C3 changed)": ch[:, 0],
            "ANY pair changed": ch.any(1),
        }
        print("\n" + "=" * 84)
        print(f"{label}   programs={n}   pairs changed (C1-3, C2-4, C5-7, C6-8): {ch.sum(0).tolist()}")
        print("=" * 84)
        v_all = ast_vec(P)
        m, lo, hi, p = boot(v_all, rng, a.boot)
        print(f"{'ALL programs (as in Table VII)':34s} n={n:4d}  AST effect {m:+.4f}  [{lo:+.4f}, {hi:+.4f}]  p={p:.4g}")
        for name, mask in subsets.items():
            k = int(mask.sum())
            if k < 20:
                print(f"{name:34s} n={k:4d}  too few programs")
                continue
            m, lo, hi, p = boot(v_all[mask], rng, a.boot)
            print(f"{name:34s} n={k:4d}  AST effect {m:+.4f}  [{lo:+.4f}, {hi:+.4f}]  p={p:.4g}")
            m2, lo2, hi2, p2 = boot(ast_by_syn_dd(P)[mask], rng, a.boot)
            print(f"{'   AST x syntheticity (DiD)':34s}          {m2:+.4f}  [{lo2:+.4f}, {hi2:+.4f}]  p={p2:.4g}")
            comp = ~mask
            print(f"{'   complement (unchanged), check':34s} n={int(comp.sum()):4d}  AST effect {(v_all[comp].mean() if comp.any() else float('nan')):+.4f}"
                  "   (expect ~0 for PRIMARY)")
        mask = subsets["PRIMARY (C1->C3 changed)"]
        if mask.sum() >= 20:
            v13 = P[:, 2] - P[:, 0]
            m, lo, hi, p = boot(v13[mask], rng, a.boot)
            print(f"{'C1->C3 pair alone, PRIMARY':34s} n={int(mask.sum()):4d}  effect     {m:+.4f}  [{lo:+.4f}, {hi:+.4f}]  p={p:.4g}")
    print("\nNote: subset selection depends only on the manifest (program text), not on model outputs,")
    print("so it is not outcome-dependent; but it is a post-hoc analysis and is reported as exploratory.")


if __name__ == "__main__":
    main()
