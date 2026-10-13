#!/usr/bin/env python3
"""complete_case.py -- drop programs with ANY missing (empty/None) condition result in ANY of the given response files, write cleaned copies (<name>_cc.json), and list what was dropped. Rule is outcome-independent: it looks only at missingness, never at values.
Usage: python3 complete_case.py a.json b.json ..."""
import json, sys, os
files = sys.argv[1:]
data = {f: json.load(open(f)) for f in files}
def missing(v):
    if v is None or v == [] or v == {}: return True
    if isinstance(v, float) and v != v: return True
    if isinstance(v, list) and any(x is None or (isinstance(x, float) and x != x) for x in v): return True
    return False
bad = {}
for f, d in data.items():
    psr = d["per_sample_results"]
    ncond = max(len(c) for c in psr.values())
    for pid, conds in psr.items():
        miss = [c for c, v in conds.items() if missing(v)] + (["<absent cell>"] if len(conds) < ncond else [])
        if miss:
            bad.setdefault(pid, {})[os.path.basename(f)] = miss
print(f"programs with a missing cell in any file: {len(bad)}")
for pid, w in sorted(bad.items()): print("  ", pid, w)
for f, d in data.items():
    n0 = len(d["per_sample_results"])
    d["per_sample_results"] = {p: c for p, c in d["per_sample_results"].items() if p not in bad}
    out = f[:-5] + "_cc.json"
    json.dump(d, open(out, "w"))
    print(f"{f}: {n0} -> {len(d['per_sample_results'])} programs, wrote {out}")
