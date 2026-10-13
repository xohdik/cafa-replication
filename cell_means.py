#!/usr/bin/env python3
"""
cell_means.py -- the eight condition means and the SIMPLE effects behind the interaction terms, with program-bootstrap CIs.

Conditions C1..C8 = (identifiers, ast, syntheticity): C1 O/O/Real, C2 O/O/Synth, C3 O/Sh/Real, C4 O/Sh/Synth,
C5 Obf/O/Real, C6 Obf/O/Synth, C7 Obf/Sh/Real, C8 Obf/Sh/Synth.
Simple effects are averaged over the AST factor (it has no detectable effect), so each is a plain "perturbed minus baseline":
  identifiers   | real code      = mean(C5,C7) - mean(C1,C3)
  identifiers   | synthetic code = mean(C6,C8) - mean(C2,C4)
  synthetic     | orig. idents   = mean(C2,C4) - mean(C1,C3)
  synthetic     | obf. idents    = mean(C6,C8) - mean(C5,C7)
Usage: python3 cell_means.py responses_deepseek_v2.json:DeepSeek responses_qwen_v2.json:Qwen   (needs paired_effects.py)
"""
import argparse
import numpy as np
from paired_effects import load

ap = argparse.ArgumentParser()
ap.add_argument("specs", nargs="+")
ap.add_argument("--boot", type=int, default=10000)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

NAMES = ["C1 orig/orig/real", "C2 orig/orig/synth", "C3 orig/shuf/real", "C4 orig/shuf/synth",
         "C5 obf/orig/real", "C6 obf/orig/synth", "C7 obf/shuf/real", "C8 obf/shuf/synth"]
SIMPLE = {
    "identifiers | real code": ([5, 7], [1, 3]),
    "identifiers | synthetic code": ([6, 8], [2, 4]),
    "synthetic | original identifiers": ([2, 4], [1, 3]),
    "synthetic | obfuscated identifiers": ([6, 8], [5, 7]),
}
rng = np.random.default_rng(a.seed)
for spec in a.specs:
    path, _, label = spec.partition(":")
    pids, A = load(path)
    P = A.mean(2)
    n = len(pids)
    idx = rng.integers(0, n, (a.boot, n))
    print("\n" + "=" * 70 + f"\n{label or path}  (programs={n})\n" + "=" * 70)
    print(f"{'condition':<22}{'accuracy':>9}   95% CI")
    for j, nm in enumerate(NAMES):
        b = P[:, j][idx].mean(1)
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"{nm:<22}{P[:, j].mean():>9.3f}   [{lo:.3f}, {hi:.3f}]")
    print(f"\n{'simple effect':<38}{'effect':>8}   95% CI")
    for nm, (hi_c, lo_c) in SIMPLE.items():
        v = P[:, [c - 1 for c in hi_c]].mean(1) - P[:, [c - 1 for c in lo_c]].mean(1)
        b = v[idx].mean(1)
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"{nm:<38}{v.mean():>+8.3f}   [{lo:+.3f}, {hi:+.3f}]")
