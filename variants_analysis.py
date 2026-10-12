#!/usr/bin/env python3
"""
variants_analysis.py BASE_RERUN VARIANT_RERUN [--boot 10000]
BASE_RERUN   : the model's original-prompt rerun with conditions 1 and 2 (e.g. rerun_ds_q4.jsonl)
VARIANT_RERUN: the rerun of the variant manifest with --conditions 2 (e.g. rerun_dsvar_n5_q4.jsonl)
Programs scored in condition 1 and 2 of the base run and in condition 2 of the variant are compared.
Reports: accuracy, penalty (generator minus real accuracy), share of first output lines equal to 10, the five most common
first lines, and the share of programs whose CORRECT first line is 10 (to separate a prior from a true answer).
Pre-registered readings (PREREG_variants.md): the preference for 10 "weakens" if its share falls by at least 10 points with a
95% interval excluding 0; the penalty "shrinks" if it moves toward 0 by at least 3 points with a 95% interval excluding 0.
"""
import argparse, json, collections
import numpy as np


def load(p):
    d = {}
    for l in open(p):
        l = l.strip()
        if l:
            r = json.loads(l)
            if r.get("status") == "ok":
                d[(r["sample_index"], r["condition_id"])] = r
    return d


def first(s):
    ls = (s or "").strip().splitlines()
    return ls[0].strip() if ls else ""


ap = argparse.ArgumentParser(); ap.add_argument("base"); ap.add_argument("var"); ap.add_argument("--boot", type=int, default=10000)
a = ap.parse_args()
B, V = load(a.base), load(a.var)
progs = sorted(s for (s, c) in B if c == 1 and (s, 2) in B and (s, 2) in V)
N = len(progs)
c1 = np.array([B[(s, 1)]["correct"] for s in progs], float)
c2 = np.array([B[(s, 2)]["correct"] for s in progs], float)
v2 = np.array([V[(s, 2)]["correct"] for s in progs], float)
t2 = np.array([first(B[(s, 2)]["prediction"]) == "10" for s in progs], float)
tv = np.array([first(V[(s, 2)]["prediction"]) == "10" for s in progs], float)
true_b = np.mean([first(B[(s, 2)]["expected"]) == "10" for s in progs]); true_v = np.mean([first(V[(s, 2)]["expected"]) == "10" for s in progs])
rng = np.random.default_rng(20261012)
idx = rng.integers(0, N, size=(a.boot, N))
def ci(x):
    d = x[idx].mean(1); return np.percentile(d, [2.5, 97.5])
pen_b, pen_v = c2 - c1, v2 - c1
dshare, dpen = tv - t2, pen_v - pen_b
print(f"programs compared: {N}")
print(f"accuracy  real {100*c1.mean():.1f}  generator base {100*c2.mean():.1f}  generator variant {100*v2.mean():.1f}")
print(f"penalty   base {100*pen_b.mean():+.1f}  variant {100*pen_v.mean():+.1f}  change {100*dpen.mean():+.1f} [{100*ci(dpen)[0]:+.1f}, {100*ci(dpen)[1]:+.1f}]")
print(f"first line = 10   base {100*t2.mean():.1f}%  variant {100*tv.mean():.1f}%  change {100*dshare.mean():+.1f} [{100*ci(dshare)[0]:+.1f}, {100*ci(dshare)[1]:+.1f}]")
print(f"correct first line = 10   base {100*true_b:.1f}%  variant {100*true_v:.1f}%")
for nm, R in (("base", B), ("variant", V)):
    c = collections.Counter(first(R[(s, 2)]["prediction"]) for s in progs)
    print(f"most common first lines ({nm}):", [(k, round(100 * v / N, 1)) for k, v in c.most_common(5)])
w = (dshare.mean() <= -0.10) and (ci(dshare)[1] < 0)
sh = (dpen.mean() >= 0.03) and (ci(dpen)[0] > 0)
print(f"pre-registered readings: preference for 10 weakens = {w};  penalty shrinks = {sh}")
