#!/usr/bin/env python3
"""
check_synth_pairing.py -- are the four synthetic conditions (C2, C4, C6, C8) built from ONE base program?
If yes, C2 and C4 hold the same statements in a different order (equal multisets of non-blank lines), and likewise C6/C8.
Usage: python3 check_synth_pairing.py manifest.json
"""
import collections
import json
import re
import sys

m = json.load(open(sys.argv[1]))
samples = m["samples"] if isinstance(m, dict) else m


def lines(src):
    return collections.Counter(l.strip() for l in src.splitlines() if l.strip())


def mask(src):
    s = re.sub(r"\b[A-Za-z_][A-Za-z_0-9]*\b", "ID", src)
    s = re.sub(r"\d+", "N", s)
    return collections.Counter(l.strip() for l in s.splitlines() if l.strip())


tot = same24 = same68 = same26_mask = 0
examples = []
for k, s in enumerate(samples):
    c = {x["condition_id"]: x.get("source_code") for x in s["conditions"]}
    if not all(c.get(i) for i in (2, 4, 6, 8)):
        continue
    tot += 1
    if lines(c[2]) == lines(c[4]):
        same24 += 1
    elif len(examples) < 2:
        examples.append((s.get("sample_index", k), c[2], c[4]))
    if lines(c[6]) == lines(c[8]):
        same68 += 1
    if mask(c[2]) == mask(c[6]):
        same26_mask += 1
print(f"samples with all four synthetic conditions built: {tot}")
print(f"C2 vs C4 same multiset of lines (same base program): {same24} ({same24 / tot:.1%})")
print(f"C6 vs C8 same multiset of lines                    : {same68} ({same68 / tot:.1%})")
print(f"C2 vs C6 same after masking identifiers & numbers   : {same26_mask} ({same26_mask / tot:.1%})")
for idx, a, b in examples:
    print(f"\n--- sample {idx}: C2 (left) vs C4 (right), first 14 lines ---")
    la, lb = a.splitlines()[:14], b.splitlines()[:14]
    for i in range(max(len(la), len(lb))):
        print(f"{(la[i] if i < len(la) else ''):<44}| {lb[i] if i < len(lb) else ''}")
print("\nNear 100% on the first two lines => the four synthetic cells share one base program.")
print("Low => each synthetic condition got its own independently generated program.")
