#!/usr/bin/env python3
"""demo8.py ORIG_RERUN ORIG8_RERUN -- original (answer 10) against answer-8 demonstration for one model (conditions 1, 2, 5, 6).
Same statistics as demo7.py: accuracy, first-line shares of 10 and 8, the five simple effects, and the change between demonstrations
with program-level bootstrap intervals (10,000 resamples)."""
import json, sys
import numpy as np

def load(p):
    d = {}
    for l in open(p):
        l = l.strip()
        if l:
            r = json.loads(l)
            if r.get("status") == "ok": d[(r["sample_index"], r["condition_id"])] = r
    return d

def first(s):
    ls = (s or "").strip().splitlines(); return ls[0].strip() if ls else ""

A, Bm = load(sys.argv[1]), load(sys.argv[2])
progs = sorted(s for (s, c) in A if c == 1 and all((s, k) in A and (s, k) in Bm for k in (1, 2, 5, 6)))
N = len(progs); print(f"{N} programs scored in conditions 1, 2, 5 and 6 under both demonstrations")
rng = np.random.default_rng(20261012); idx = rng.integers(0, N, size=(10000, N))
def M(D): return {k: np.array([D[(s, k)]["correct"] for s in progs], float) for k in (1, 2, 5, 6)}
def eff(m): return {"S|orig": m[2] - m[1], "S|obf": m[6] - m[5], "I|real": m[5] - m[1], "I|synth": m[6] - m[2], "IxS": (m[6] - m[2]) - (m[5] - m[1])}
def fmt(x):
    lo, hi = np.percentile(x[idx].mean(1), [2.5, 97.5]); return f"{100*x.mean():+.1f} [{100*lo:+.1f}, {100*hi:+.1f}]"
res = {}
for nm, D in (("orig (answer 10)", A), ("orig8 (answer 8)", Bm)):
    m = M(D); e = eff(m); res[nm] = e
    print(f"{nm}: acc " + " ".join(f"C{k} {m[k].mean():.3f}" for k in (1, 2, 5, 6)))
    for tag in ("10", "8"):
        print(f"   first line = {tag}: " + " ".join(f"C{k} {100*np.mean([first(D[(s,k)]['prediction'])==tag for s in progs]):.1f}%" for k in (1, 2, 5, 6)))
    for k, v in e.items(): print(f"     {k:8s} {fmt(v)}")
k0, k1 = list(res)
print(f"  orig8 minus orig, S|orig: {fmt(res[k1]['S|orig'] - res[k0]['S|orig'])}")
print(f"  orig8 minus orig, IxS:    {fmt(res[k1]['IxS'] - res[k0]['IxS'])}")
