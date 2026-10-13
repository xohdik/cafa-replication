#!/usr/bin/env python3
"""
format_confound.py -- is the AST-shuffle contrast contaminated by reformatting?

C1 is the original source text; shuffled conditions pass through an AST round-trip that rewrites
formatting and drops comments. So C1 -> C3 differs in TEXT even when the statements were not
reordered. For each AST pair (C1->C3, C2->C4, C5->C7, C6->C8) and each program, the manifest puts
the program in exactly one group:
  IDENTICAL  : same text         -> the prompt is the same; the score difference must be exactly 0
  FORMAT-ONLY: same syntax tree, different text -> pure presentation change, no reordering
  REORDERED  : different syntax tree             -> an actual shuffle
Per model and pair we report the group sizes and the mean score change in each group (program-level
bootstrap CI). The FORMAT-ONLY mean is a direct estimate of the reformatting effect.

Usage: python3 -W ignore format_confound.py --manifest manifest.json responses_deepseek.json:DeepSeek responses_qwen.json:Qwen
Requires paired_effects.py in the same directory.
"""
import argparse
import ast
import json
import numpy as np
from paired_effects import load

PAIRS = [(1, 3), (2, 4), (5, 7), (6, 8)]


def tree(src):
    try:
        return ast.dump(ast.parse(src))
    except SyntaxError:
        return None


def groups(manifest_path, pids):
    m = json.load(open(manifest_path))
    samples = m["samples"] if isinstance(m, dict) else m
    g = {}
    for pos, s in enumerate(samples):
        src = {c["condition_id"]: c["source_code"] for c in s["conditions"]}
        row = []
        for b, t in PAIRS:
            if src[b] == src[t]:
                row.append(0)                     # IDENTICAL
            else:
                tb, tt = tree(src[b]), tree(src[t])
                row.append(1 if (tb is not None and tb == tt) else 2)   # FORMAT-ONLY / REORDERED
        g[str(s.get("sample_index", pos))] = row
    missing = [p for p in pids if p not in g]
    if missing:
        raise SystemExit(f"{len(missing)} ids missing from manifest, e.g. {missing[:5]}")
    return np.array([g[p] for p in pids])


def boot(v, rng, B=10000):
    idx = rng.integers(0, len(v), (B, len(v)))
    b = v[idx].mean(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return v.mean(), lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    names = {0: "IDENTICAL   ", 1: "FORMAT-ONLY ", 2: "REORDERED   "}
    for spec in a.specs:
        path, _, label = spec.partition(":")
        pids, A = load(path)
        P = A.mean(2)
        G = groups(a.manifest, pids)
        print("\n" + "=" * 86)
        print(label)
        print("=" * 86)
        for j, (b, t) in enumerate(PAIRS):
            d = P[:, t - 1] - P[:, b - 1]
            print(f"\n pair C{b}->C{t}")
            for code in (0, 1, 2):
                mk = G[:, j] == code
                k = int(mk.sum())
                if k == 0:
                    print(f"   {names[code]} n={k:4d}")
                    continue
                if code == 0:
                    print(f"   {names[code]} n={k:4d}  max |diff| = {np.abs(d[mk]).max():.3f}   (must be 0)")
                elif k >= 20:
                    m, lo, hi = boot(d[mk], rng)
                    print(f"   {names[code]} n={k:4d}  mean change {m:+.4f}  [{lo:+.4f}, {hi:+.4f}]")
                else:
                    print(f"   {names[code]} n={k:4d}  mean change {d[mk].mean():+.4f}  (too few for a CI)")
    print("\nFORMAT-ONLY rows estimate the effect of reformatting alone. If it is comparable to the")
    print("identifier or AST effects in Table VII, those effects cannot be attributed to the named factor.")


if __name__ == "__main__":
    main()
