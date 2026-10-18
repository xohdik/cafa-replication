#!/usr/bin/env python3
"""g2_check.py -- is the G2 run complete and sane? Counts cells and statuses per output file against manifest_g2.json, and prints accuracy by condition."""
import collections, glob, json, os, sys

man = json.load(open("manifest_g2.json"))
N = len(man["samples"])
exp = {}
for t in ("ds", "sc2", "cl", "q7", "q14"):
    exp[f"g2_out/e1_{t}.jsonl"] = (N, (2, 4, 6, 8)); exp[f"g2_out/e2_{t}.jsonl"] = (N, (2, 6))
for t in ("yi9", "cg7", "gr3", "sc3", "q3", "q15", "ds13", "sc15", "cl13", "gr8"):
    exp[f"g2_out/e3_{t}_orig.jsonl"] = (N, (2,)); exp[f"g2_out/e3_{t}_none.jsonl"] = (N, (2,))
bad = 0
print(f"{N} samples in manifest_g2.json; {'file':34s} cells  expected  ok  skip_*  error  | accuracy by condition (ok cells)")
for f, (n, conds) in exp.items():
    if not os.path.exists(f):
        print(f"MISSING {f}"); bad += 1; continue
    recs = {}
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        recs[(r["sample_index"], r["condition_id"])] = r
    st = collections.Counter(("ok" if r["status"] == "ok" else "error" if r["status"].startswith("error") else "skip") for r in recs.values())
    want = n * len(conds)
    acc = {}
    for c in conds:
        ok = [r["correct"] for (s, cc), r in recs.items() if cc == c and r["status"] == "ok"]
        acc[c] = (sum(ok) / len(ok) if ok else float("nan"), len(ok))
    flag = "" if len(recs) == want and st["error"] == 0 else "   <-- CHECK"
    if flag: bad += 1
    print(f"{f:34s} {len(recs):5d} {want:8d} {st['ok']:5d} {st['skip']:5d} {st['error']:5d}  | " + "  ".join(f"c{c}={a:.3f}(n={k})" for c, (a, k) in acc.items()) + flag)
print("\nPROBLEMS:", bad if bad else "none")
for lg in sorted(glob.glob("g2_out/log_gpu*.txt")):
    tail = open(lg).read().strip().splitlines()[-1:]
    errs = sum(1 for l in open(lg) if "Traceback" in l or "Error" in l)
    print(lg, "| last line:", tail, "| lines with Traceback/Error:", errs)
