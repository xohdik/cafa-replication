#!/usr/bin/env python3
"""show_example.py -- print one sample of the confirmation manifest in conditions 1, 2, 5, 6, with the expected
output and the DeepSeek-Coder prediction. Usage: python3 show_example.py manifest_confirm.json rerun_ds_q4.jsonl [N]
Prints up to N candidate samples (default 6): short real program, short generator program with dead _pad lines,
one-line expected output, real program answered correctly and generator program answered wrongly."""
import json, sys, io, contextlib, subprocess
man = json.load(open(sys.argv[1])); rr = {}
for l in open(sys.argv[2]):
    l = l.strip()
    if l:
        r = json.loads(l); rr[(r["sample_index"], r["condition_id"])] = r
N = int(sys.argv[3]) if len(sys.argv) > 3 else 6
shown = 0
cands = []
for s in man["samples"]:
    cs = {b["condition_id"]: b for b in s["conditions"] if b.get("status") == "ok"}
    if not all(c in cs for c in (1, 2, 5, 6)): continue
    r1, r2 = rr.get((s["sample_index"], 1)), rr.get((s["sample_index"], 2))
    if not r1 or not r2 or r1.get("status") != "ok" or r2.get("status") != "ok": continue
    n1 = len(cs[1]["source_code"].strip().splitlines()); n2 = len(cs[2]["source_code"].strip().splitlines())
    if n1 > 9 or n2 > 14: continue
    if "\n" in (r1.get("expected") or "").strip(): continue
    if not r1["correct"] or r2["correct"]: continue
    if "_pad" not in cs[2]["source_code"]: continue
    cands.append((n1 + n2, s, cs, r1, r2))
cands.sort(key=lambda x: x[0])
for _, s, cs, r1, r2 in cands[:N]:
    print("=" * 78); print("sample_index", s["sample_index"], "problem", s.get("problem_id"))
    for c in (1, 2, 5, 6):
        print(f"--- condition {c}  stdin={cs[c].get('stdin_cases') or s.get('stdin_cases')}")
        print(cs[c]["source_code"].strip())
    print("--- expected (cond 1):", repr(r1.get("expected")), " DeepSeek cond 1:", repr(r1.get("prediction")))
    print("--- expected (cond 2):", repr(r2.get("expected")), " DeepSeek cond 2:", repr(r2.get("prediction")))
print(len(cands), "candidates")
